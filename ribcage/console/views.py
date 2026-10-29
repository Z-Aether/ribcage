from contextlib import suppress
from dataclasses import replace

from django.conf import settings
from django.http import FileResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from ribcage.ballot import floor, progress
from ribcage.console import films
from ribcage.console.forms import BackupCodeForm, BackupUploadForm
from ribcage.console.moves import make, offered
from ribcage.identity import admin_session
from ribcage.identity.admin_session import admin_required
from ribcage.identity.models import Voter
from ribcage.identity.removal import remove, what_goes
from ribcage.identity.reset import password_digest, reset
from ribcage.operations import offer
from ribcage.operations.backup import describe
from ribcage.ballot.board import candidates
from ribcage.phase.history import current, last_entered, vote_has_opened
from ribcage.phase.order import PHASES, MoveRefused, Phase
from ribcage.reload import reload_the_tab
from ribcage.suggestions import runtime
from ribcage.suggestions.models import Suggestion
from ribcage.timetable import editing, engine, labelling, laying, offering, retiming, setting, track
from ribcage.timetable import plan
from ribcage.timetable.models import Box
from ribcage.triggers import correction, stored

# Where each phase's work is: Films through VOTE, Pick from PICK on (#28).
WORKING_TABS = {
    Phase.SUGGEST: "console_films",
    Phase.APPROVE: "console_films",
    Phase.VOTE: "console_films",
    Phase.PICK: "console_pick",
    Phase.RUN: "console_pick",
}


def render_tab(request, template, context=None, phase=None):
    # Every tab carries the current phase, as a badge on the Phase tab (#28).
    return render(request, template, {"phase": phase or current(), **(context or {})})


@admin_required
def console(request):
    # Only the landing follows the phase; each tab keeps its own address, so it stays put when the phase moves (#28).
    return redirect(WORKING_TABS[current()])


@admin_required
def phase_tab(request):
    phase = current()
    # Arming is a plain GET that moves nothing; an arm from a tab whose phase is stale arms nothing (#28, #77).
    armed_to = request.GET.get("arm") if request.GET.get("from") == phase else None
    entered = last_entered()
    context = {
        "phases": [(each, entered.get(each)) for each in PHASES],
        "moves": offered(phase, armed_to),
        "voters": Voter.objects.count(),
        "films": films.status(),
        "done": films.done_so_far(),
    }
    return render_tab(request, "console/phase.html", context, phase)


@admin_required
@require_POST
def move_phase(request):
    # The post names the phase it expects to leave, so a stale tab moves nothing and reloads into the phase as it is (#74, #77).
    with suppress(MoveRefused):
        make(request.POST.get("from_phase"), request.POST.get("to_phase"))
    return redirect("console_phase")


def armed_approval(request, ledger):
    """The row whose Approve is armed and what it costs, when VOTE has opened and the row still offers Approve; else nothing (#124)."""
    cost = films.cost_of_approving()
    wanted = request.GET.get("arm", "")
    row = next((each for each in ledger.rows if str(each.card.suggestion_id) == wanted and each.may_approve), None)
    return (row.card.suggestion_id, cost) if row and cost else (None, cost)


def render_films(request, show, refused=None):
    ledger = films.ledger(show)
    armed, cost = armed_approval(request, ledger)
    context = {
        "ledger": ledger,
        "screen_time": films.screen_time_words(ledger.screen_time),
        "refused": refused,
        "tab": "console_films",
        "done": films.done_so_far(),
        "asks_first": cost is not None,
        "armed": armed,
        "cost": cost,
    }
    return render_tab(request, "console/films.html", context)


@admin_required
def films_tab(request):
    # A filter is a plain link, so the tab needs no script to read it (the dev, 2026-10-23, on #61).
    return render_films(request, films.chosen(request.GET.get("show")))


@admin_required
@require_safe
def films_dtdd(request):
    """An opened card's full DoesTheDogDie topic list, fetched as it first opens under its row; the one every voter sees (#35 §2, #103)."""
    if request.headers.get("HX-Request") != "true":
        return redirect("console_films")
    try:
        suggestion = Suggestion.objects.filter(pk=request.GET.get("suggestion")).first()
    except (TypeError, ValueError):
        suggestion = None
    # Withdrawn since, or the marathon in RUN, which shows no trigger data: the tab reloads as it is now (#106).
    if suggestion is None or current() == Phase.RUN:
        return reload_the_tab(request, reverse("console_films"))
    return render(request, "components/dtdd_topics.html", {"dtdd": stored.section_of(suggestion)})


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
def films_match(request):
    """The admin's correction of a match under a row, never phase-gated: a GET previews or cancels, and the POST saves it (#78, #105)."""
    try:
        suggestion = Suggestion.objects.filter(pk=request.POST.get("suggestion") or request.GET.get("suggestion")).first()
    except (TypeError, ValueError):
        suggestion = None
    # Withdrawn since: the tab reloads as it is now.
    if suggestion is None:
        return reload_the_tab(request, reverse("console_films"))
    if request.method == "POST":
        try:
            correction.use(suggestion, request.POST.get("snapshot", ""), correction.BY_THE_ADMIN)
        except correction.Tampered:
            return HttpResponseBadRequest()
    # RUN offers no control and shows no section, so a stale tab reloads as it is now (#106).
    if current() == Phase.RUN:
        return reload_the_tab(request, reverse("console_films"))
    # Only htmx swaps the section in place; a plain request lands on the tab.
    if request.headers.get("HX-Request") != "true":
        return redirect("console_films")
    card = films.the_card(suggestion)
    if request.method != "POST" and "cancel" not in request.GET:
        card = replace(card, dtdd=correction.previewed(card.dtdd, suggestion, request.GET.get("link", "")))
    return render(request, "components/dtdd_section.html", {"card": card, "dtdd": card.dtdd, "answers_the_control": True})


@admin_required
@require_POST
def decide_approval(request):
    # The post is the confirm, whatever the phase, and reloads with no message onto the filter it was sent from, whatever it changed (#28, #77, #96, #124).
    post = request.POST
    films.decide(post.get("suggestion"), post.get("from_approval"), post.get("to_approval"))
    return redirect(films.chosen(post.get("show")).address)


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
def edit_runtime(request):
    # A GET is a reload onto the page a refusal was shown at, so it lands on the tab (#80, #97).
    show = films.chosen(request.POST.get("show"))
    if request.method != "POST":
        return redirect(show.address)
    # A refusal renders the tab here under the posted filter, as the typed value has to stay in its box (#97).
    if refused := films.edit_runtime(request.POST.get("suggestion"), request.POST.get("runtime", "")):
        return render_films(request, show, refused)
    return redirect(show.address)


def selected_box(request, chosen=None):
    """The box the tab's address selects, as an id, or None for none or nonsense (#137); a refused save names its own (#138)."""
    chosen = request.GET.get("box", "") if chosen is None else chosen
    return int(chosen) if chosen.isascii() and chosen.isdigit() and len(chosen) < 10 else None


# The ripple mode control's words, in the tool row's order (#140, #141).
RIPPLE_NAMES = ((engine.NONE, "None"), (engine.KEEP_GAPS, "Push · keep gaps"), (engine.KEEP_END_TIME, "Push · keep end time"))
RIPPLE_SESSION_KEY = "ripple_mode"


def ripple_mode(request):
    """The admin's sticky ripple mode, kept in their session; None until set (#13, #140)."""
    mode = admin_session.kept(request, RIPPLE_SESSION_KEY, engine.NONE)
    return mode if mode in engine.MODES else engine.NONE


def track_context(request, mode=None):
    # The timetable and the break the tool row reads, for every render of the track, a preview's included (#145).
    return {"ripple_mode": mode or ripple_mode(request), "ripple_names": RIPPLE_NAMES, "timetable": setting.read(), "default_break": engine.DEFAULT_BREAK}


# The arrange utilities' words, for the tool row (#145).
ARRANGE_NAMES = {engine.LAY_OUT: "Lay out with a break", engine.SPREAD: "Spread evenly"}


def arrange_asked(data):
    """The utility and break a request names, or None where it names none or a nonsense one (#145)."""
    utility = data.get("arrange")
    if utility not in engine.UTILITIES:
        return None
    if utility == engine.SPREAD:
        return utility, 0
    minutes = editing.valid_break(data.get("minutes", engine.DEFAULT_BREAK))
    return None if minutes is None else (utility, minutes)


def armed_context(asked):
    """What the tool row needs to show an utility armed: its name and its break, or nothing."""
    return {"armed": {"utility": asked[0], "minutes": asked[1], "name": ARRANGE_NAMES[asked[0]]} if asked else None, "arrange_names": ARRANGE_NAMES, "default_break": engine.DEFAULT_BREAK}


def render_pick(request, sub, refused=None, box_refused=None, box=None, mode=None, runtime_refused=None):
    """The Pick tab on one of its two sub-tabs; the header is the same on both (#135)."""
    timetable = setting.read()
    budget = timetable.budget
    the_track = track.load(timetable.anchor, budget) if sub == "timetable" and timetable.anchor else None
    labelled = selected_box(request, box)
    # Arming is a plain GET: the arranged track in place of the stored one, nothing written (#26, #145).
    armed = arrange_asked(request.GET) if request.method == "GET" and the_track else None
    if armed and (arranged := editing.arrange(*armed, save=False)):
        the_track = track.build(arranged, timetable.anchor, budget)
    else:
        armed = None
    if the_track and box_refused and not box_refused.says_length and Box.objects.filter(pk=labelled, suggestion__isnull=True).exists():
        # A refusal over the label alone keeps the typed length, so the track keeps showing it as the preview did (#140).
        kept = editing.run(labelled, engine.Resize(int(box_refused.length.strip())), mode or ripple_mode(request), save=False)
        the_track = track.build(kept, timetable.anchor, budget) if kept else the_track
    context = {
        "tab": "console_pick",
        "sub": sub,
        "timetable": timetable,
        "anchor": setting.local_anchor(timetable.anchor),
        "budget_hours": None if budget is None else budget // 60,
        "budget_minutes": None if budget is None else budget % 60,
        "budget_words": None if budget is None else films.screen_time_words(budget),
        "refused": refused,
        "track": the_track,
        "selected": the_track.box(labelled) if the_track else None,
        "box_refused": box_refused,
        "runtime_refused": runtime_refused,
        **track_context(request, mode),
        **armed_context(armed),
        "candidates": offering.not_in_the_plan() if sub == "timetable" else (),
        "plan": plan.load() if sub == "compare" else None,
    }
    return render_tab(request, "console/pick.html", context)


@admin_required
def pick_tab(request):
    # The Pick tab opens on Timetable (#135).
    return render_pick(request, "timetable")


@admin_required
def pick_compare(request):
    return render_pick(request, "compare")


def chosen_sub(request):
    return "compare" if request.POST.get("sub") == "compare" else "timetable"


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
def pick_anchor(request):
    # A GET is a reload onto the page a refusal was shown at, so it lands on the tab; never phase-gated (#15, #28, #135).
    if request.method != "POST":
        return redirect("console_pick")
    if refused := setting.set_anchor(request.POST.get("anchor", "")):
        return render_pick(request, chosen_sub(request), refused)
    return redirect("console_pick_compare" if chosen_sub(request) == "compare" else "console_pick")


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
def pick_budget(request):
    if request.method != "POST":
        return redirect("console_pick")
    if refused := setting.set_budget(request.POST.get("hours", ""), request.POST.get("minutes", "")):
        return render_pick(request, chosen_sub(request), refused)
    return redirect("console_pick_compare" if chosen_sub(request) == "compare" else "console_pick")


@admin_required
@require_POST
def pick_add(request):
    # A stale or repeated post changes nothing and reloads the tab as it is now; never phase-gated (#28, #137).
    box = laying.lay_film(request.POST.get("suggestion"))
    return reload_the_tab(request, reverse("console_pick") + (f"?box={box.pk}" if box else ""))


@admin_required
@require_POST
def pick_remove(request):
    laying.take_off(request.POST.get("box"))
    return reload_the_tab(request, reverse("console_pick"))


@admin_required
@require_POST
def pick_break(request):
    box = laying.lay_break()
    return reload_the_tab(request, reverse("console_pick") + (f"?box={box.pk}" if box else ""))


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
def pick_box(request):
    # A GET is a reload onto the page a refusal was shown at, so it lands on the tab (#135, #138).
    if request.method != "POST":
        return redirect("console_pick")
    # A refusal renders the tab with the box still selected and the typing kept; a box gone since reloads as it is (#138).
    box = request.POST.get("box", "")
    mode = request.POST.get("mode", "")
    mode = mode if mode in engine.MODES else ripple_mode(request)
    if refused := labelling.save(box, request.POST.get("label", ""), request.POST.get("length", ""), mode, "flexible" in request.POST):
        return render_pick(request, "timetable", box_refused=refused, box=box, mode=mode)
    return reload_the_tab(request, reverse("console_pick") + (f"?box={box}" if selected_box(request, box) else ""))


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
def pick_runtime(request):
    # A film box's runtime, saved through the ripple mode with what it pushes; a refusal keeps the box selected and the typing (#142).
    if request.method != "POST":
        return redirect("console_pick")
    box = request.POST.get("box", "")
    mode = request.POST.get("mode", "")
    mode = mode if mode in engine.MODES else ripple_mode(request)
    if refused := retiming.save(box, request.POST.get("runtime", ""), mode):
        return render_pick(request, "timetable", runtime_refused=refused, box=box, mode=mode)
    return reload_the_tab(request, reverse("console_pick") + (f"?box={box}" if selected_box(request, box) else ""))


def edit_asked(request, typed_lengths=False):
    """The box, the change and the mode a post names, or None where the post is no edit's (#139, #140).

    A drag's post names a `start`. A typed `length` is the preview's alone, as the save is `labelling.save`'s: only the
    preview asks with `typed_lengths`, and a `length` the save would refuse is a Resize of nothing, left to the caller.
    """
    box = selected_box(request, request.POST.get("box", ""))
    mode = request.POST.get("mode", engine.NONE)
    if box is None or mode not in engine.MODES:
        return None
    if typed_lengths and "runtime" in request.POST:
        typed = request.POST["runtime"]
        if not Box.objects.filter(pk=box, suggestion__isnull=False).exists():
            return None
        return box, (None if retiming.refusal(typed) else engine.Resize(runtime.minutes(typed))), mode
    if typed_lengths and "length" in request.POST:
        typed = request.POST["length"]
        # A film's is no length, but a box gone since is the reload's, like a drag's (#143).
        if Box.objects.filter(pk=box, suggestion__isnull=False).exists():
            return None
        return box, (None if labelling.length_refusal(typed) else engine.Resize(int(typed.strip()))), mode
    start = editing.valid_start(request.POST.get("start"))
    return None if start is None else (box, engine.Move(start), mode)


def kept_scale(request):
    """The scale a drag holds still, from the post, or None to fit the evening afresh (#139)."""
    try:
        start, length = int(request.POST["scale_start"]), int(request.POST["scale_length"])
    except (KeyError, ValueError):
        return None
    return track.Scale(start, length) if 0 < length <= 2 * editing.FURTHEST and abs(start) <= editing.FURTHEST else None


@admin_required
@require_POST
def pick_preview(request):
    # The same edit as the save, writing nothing: the answer is the track and tool row alone, for the browser to morph in (#22, #139).
    if "suggestion" in request.POST:
        return preview_insert(request)
    if "arrange" in request.POST:
        return preview_arrange(request)
    if not (asked := edit_asked(request, typed_lengths=True)):
        return HttpResponseBadRequest()
    box, change, mode = asked
    timetable = setting.read()
    # A typed length passes through values the save would refuse, like the 9 of 90: those show the stored track, not an error (#140).
    if not timetable.anchor:
        boxes = None
    elif change is None:
        boxes = track.stored_boxes()
        boxes = boxes if any(each.key == box for each in boxes) else None
    else:
        boxes = editing.run(box, change, mode, save=False)
    if boxes is None:
        return reload_the_tab(request, reverse("console_pick"))
    the_track = track.build(boxes, timetable.anchor, timetable.budget, kept_scale(request))
    return render(request, "console/track.html", {**track_context(request, mode), "track": the_track, "selected": the_track.box(selected_box(request, request.POST.get("selected", "")))})


def insert_asked(request):
    """The film, start and mode a candidate's drag names, or None where the post is no insert's (#144)."""
    start = editing.valid_start(request.POST.get("start"))
    mode = request.POST.get("mode", engine.NONE)
    film = request.POST.get("suggestion")
    return None if film is None or start is None or mode not in engine.MODES else (film, start, mode)


def preview_insert(request):
    if not (asked := insert_asked(request)):
        return HttpResponseBadRequest()
    boxes = editing.insert(*asked, save=False)
    # A film placed or dropped since reloads the tab as it is now (#26 §5, #144).
    if boxes is None:
        return reload_the_tab(request, reverse("console_pick"))
    timetable = setting.read()
    the_track = track.build(boxes, timetable.anchor, timetable.budget, kept_scale(request))
    return render(request, "console/track.html", {**track_context(request, asked[2]), "track": the_track, "selected": the_track.box(selected_box(request, request.POST.get("selected", "")))})


def preview_arrange(request):
    # An armed utility, shown through the preview's template; it ignores the mode but the forms on the track post the page's (#145).
    if not (asked := arrange_asked(request.POST)):
        return HttpResponseBadRequest()
    boxes = editing.arrange(*asked, save=False)
    if boxes is None:
        return reload_the_tab(request, reverse("console_pick"))
    timetable = setting.read()
    the_track = track.build(boxes, timetable.anchor, timetable.budget, kept_scale(request))
    return render(request, "console/track.html", {**track_context(request), **armed_context(asked), "timetable": timetable, "track": the_track, "selected": the_track.box(selected_box(request, request.POST.get("selected", "")))})


@admin_required
@require_POST
def pick_arrange(request):
    # Apply: the utility again over the timetable as stored now, saving; the tab reloads unarmed (#145).
    if not (asked := arrange_asked(request.POST)):
        return HttpResponseBadRequest()
    editing.arrange(*asked, save=True)
    kept = selected_box(request, request.POST.get("selected", ""))
    return reload_the_tab(request, reverse("console_pick") + (f"?box={kept}" if kept and Box.objects.filter(pk=kept).exists() else ""))


@admin_required
@require_POST
def pick_place(request):
    # A candidate dropped on the track: the preview's call, saving. The new box is selected; a film gone from the list changes nothing (#144).
    if not (asked := insert_asked(request)):
        return HttpResponseBadRequest()
    boxes = editing.insert(*asked, save=True)
    return reload_the_tab(request, reverse("console_pick") + (f"?box={boxes[-1].key}" if boxes else ""))


@admin_required
@require_POST
def pick_move(request):
    # The release: the preview's call, saving. A box gone since reloads the tab as it is now (#139).
    if not (asked := edit_asked(request)):
        return HttpResponseBadRequest()
    box, change, mode = asked
    kept = editing.run(box, change, mode, save=True) if setting.read().anchor else None
    return reload_the_tab(request, reverse("console_pick") + (f"?box={box}" if kept else ""))


@admin_required
@require_POST
def pick_resize(request):
    # The handle's release: a labelled box's length, saved by `labelling.resize` so `labelling.save` stays its one write (#143).
    box = selected_box(request, request.POST.get("box", ""))
    mode = request.POST.get("mode", engine.NONE)
    if box is None or mode not in engine.MODES:
        return HttpResponseBadRequest()
    if labelling.resize(box, request.POST.get("length", ""), mode):
        return HttpResponseBadRequest()
    return reload_the_tab(request, reverse("console_pick") + (f"?box={box}" if Box.objects.filter(pk=box).exists() else ""))


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
def pick_mode(request):
    # The mode is sticky in the admin's session; the tab reloads so every form on it names the mode the page shows (#140).
    if request.method == "POST" and request.POST.get("mode") in engine.MODES:
        admin_session.keep(request, RIPPLE_SESSION_KEY, request.POST["mode"])
    kept = selected_box(request, request.POST.get("selected", "")) if request.method == "POST" else None
    return reload_the_tab(request, reverse("console_pick") + (f"?box={kept}" if kept else ""))


def named_voter(pk):
    """The voter a form or a link names by id, or None for an id that names nobody, or no id at all (#79)."""
    try:
        return Voter.objects.filter(pk=pk).first()
    except (TypeError, ValueError):
        return None


def render_roster(request, context):
    # The one row open under its voter: an armed act's confirm, or the password a reset just made (#79, #80).
    open_row = context.get("armed") or context.get("was_reset")
    voters = list(Voter.objects.order_by("display_name_key", "pk"))
    # Progress reads *—* until VOTE has opened (#28, #124).
    opened = vote_has_opened()
    shown = {each.voter_id: each for each in progress.of_every_voter()} if opened else {}
    for voter in voters:
        voter.progress = shown.get(voter.pk)
    ballot_size = candidates().count() if opened else 0
    floor_line, out_for = floor.of_the_roster()
    for voter in voters:
        voter.out_for = out_for.get(voter.pk)
    return render_tab(
        request,
        "console/roster.html",
        {"voters": voters, "ballot_size": ballot_size, "floor_line": floor_line, "floor_opened": opened, "tab": "console_roster", "open_row": open_row, **context},
    )


def armed_reset(voter, used=False):
    return {"armed": voter, "arming": "reset", "replacing": password_digest(voter), "used": used}


@admin_required
def roster_tab(request):
    # Arming is a plain GET that changes nothing, naming the voter by id; a row arms one act at a time (#28, #79, #80).
    if armed := named_voter(request.GET.get("remove")):
        return render_roster(request, {"armed": armed, "arming": "remove", "goes": what_goes(armed)})
    if armed := named_voter(request.GET.get("reset")):
        return render_roster(request, armed_reset(armed))
    return render_roster(request, {})


@admin_required
@require_POST
def remove_voter(request):
    # A confirm for a voter already removed, or for nobody, removes nobody and reloads the tab (#79).
    if voter := named_voter(request.POST.get("voter")):
        remove(voter)
    return redirect("console_roster")


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
@never_cache
def reset_password(request):
    # A GET is a reload onto the page a reset's result was shown at, so it lands on the Roster tab (#76, #80).
    if request.method != "POST":
        return redirect("console_roster")
    # The password is in this response alone, never a redirect's target, so no reload or address can show it again (#80).
    voter = named_voter(request.POST.get("voter"))
    password = voter and reset(voter, request.POST.get("replacing"))
    if password:
        return render_roster(request, {"was_reset": voter, "password": password})
    # Re-read, as the view's copy may predate the reset that refused this confirm, and its digest would be the one just used (#80).
    if voter and (voter := named_voter(voter.pk)):
        # A confirm out of date (a double click, a reload's resubmit) is refused, so say so and offer a fresh one (#80).
        return render_roster(request, armed_reset(voter, used=True))
    return redirect("console_roster")


REFUSALS = {
    offer.NoOffer: "No backup is on offer. Make a code first, in the ribcage container's terminal.",
    offer.Expired: "That code had expired, so the offer is void. Make a new code.",
    offer.WrongCode: "That code is wrong, so the offer is void. Make a new code.",
    offer.WrongPurpose: "That code was made for an upload, so the offer is void. Make a new code with backupcode download.",
}
UPLOAD_REFUSALS = {
    offer.NoOffer: "No code is on offer. Make one first, in the ribcage container's terminal.",
    offer.Expired: "That code had expired, so it is void and the file was not kept. Make a new code.",
    offer.WrongCode: "That code is wrong, so it is void and the file was not kept. Make a new code.",
    offer.WrongPurpose: "That code was made for a download, so it is void and the file was not kept. Make a new code with backupcode upload.",
    offer.TooLarge: f"That file is over {offer.UPLOAD_CAP_MB} MB, far larger than a marathon's backup, so it was not kept. The code wasn't tried, so if it was right it still works.",
    offer.NotADatabase: "That file is not an SQLite database, so it was not kept. The code wasn't tried, so if it was right it still works.",
    offer.FailsIntegrityCheck: "That file failed SQLite's integrity check, so it was not kept. The code wasn't tried, so if it was right it still works.",
}


def render_backup(request, **context):
    # An upload's answer is at the upload's address, so name the tab it belongs to (#86).
    return render_tab(request, "console/backup.html", {"form": BackupCodeForm(), "upload_form": BackupUploadForm(), "tab": "console_backup", **context})


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
def backup_page(request):
    # A tab, yet only a code from the shell yields the database, never the admin password alone (#54, #68, #86).
    form = BackupCodeForm(request.POST if request.method == "POST" else None)
    if not form.is_valid():
        offer.void_if_expired(settings.BACKUP_OFFER_DIRECTORY, timezone.now())
        return render_backup(request, form=form)
    try:
        redeemed = offer.redeem(settings.BACKUP_OFFER_DIRECTORY, form.cleaned_data["code"], timezone.now(), offer.DOWNLOAD)
    except offer.Refused as refusal:
        return render_backup(request, refusal=REFUSALS[type(refusal)])
    response = FileResponse(offer.opened(redeemed), as_attachment=True, filename=redeemed.file.name, content_type="application/octet-stream")
    response["Cache-Control"] = "no-store"
    return response


def skipped_over_the_cap(request):
    # The upload handler drops a file over the cap, so only the body's length is left to tell it from no file (#81).
    return "backup" not in request.FILES and int(request.META.get("CONTENT_LENGTH") or 0) > offer.UPLOAD_CAP_BYTES


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
def upload_backup(request):
    # A GET is a reload onto the page an upload's result was shown at, so it lands on the backup page (#76, #81).
    if request.method != "POST":
        return redirect("console_backup")
    # The page only keeps the file, beside the database; the restore is a step in the sidecar's terminal (#81).
    if skipped_over_the_cap(request):
        return refused_upload(request, offer.TooLarge, request.POST.get("code", ""))
    form = BackupUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return render_backup(request, upload_form=form)
    try:
        kept, counts = offer.accept_upload(
            settings.BACKUP_OFFER_DIRECTORY,
            form.cleaned_data["code"],
            form.cleaned_data["backup"].chunks(),
            settings.BACKUP_UPLOAD_DIRECTORY,
            timezone.now(),
        )
    except (offer.Refused, offer.Unkept) as refusal:
        return refused_upload(request, type(refusal), form.cleaned_data["code"])
    return render_backup(request, kept=kept.name, kept_counts=describe(counts), upload_directory=settings.BACKUP_UPLOAD_DIRECTORY)


def refused_upload(request, refusal, code):
    # A file refused for what it is never tries the code, so it stays in the field for the right file (#81).
    still_works = issubclass(refusal, offer.Unkept)
    return render_backup(request, upload_refusal=UPLOAD_REFUSALS[refusal], upload_form=BackupUploadForm(initial={"code": code if still_works else ""}))
