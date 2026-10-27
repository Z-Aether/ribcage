from dataclasses import replace

from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_safe

from ribcage.films import find as find_text
from ribcage.films import signed
from ribcage.films.client import NotAnswering, tmdb_client
from ribcage.films.film import hand_entered
from ribcage.films.picker import Picker

from ribcage.phase.check import phase_window
from ribcage.phase.history import current
from ribcage.phase.order import Phase
from ribcage.reload import reload_the_tab
from ribcage.suggestions import notes, picker, pitch, pool, saving, withdrawal
from ribcage.suggestions.models import Suggestion
from ribcage.films.card import Watch
from ribcage.triggers import correction, stored, watched
from ribcage.triggers.views import WRITING, posted_tick

def named_suggestion(pk):
    """The suggestion a post names by id, or None for one withdrawn since, or no id at all (#88, #89)."""
    try:
        return withdrawal.with_holds(Suggestion.objects.filter(pk=pk)).first()
    except (TypeError, ValueError):
        return None


@phase_window(Phase.SUGGEST, Phase.APPROVE)
@require_POST
def write_note(request):
    """The card's one Save: the note, and the runtime where its box was open, written together or not at all (#88, #133)."""
    # The card the post came from is gone, so the tab reloads onto the pool as it is now (#89).
    if (suggestion := named_suggestion(request.POST.get("suggestion"))) is None:
        return reload_the_tab(request, reverse("phase_page"))
    typed = request.POST.get("text", "")
    # None where the box was shut, so the note is saved alone (#133).
    typed_runtime = request.POST.get("runtime")
    phase = current()
    card = pool.the_card(suggestion, request.user, phase)
    refusals = saving.save(suggestion, request.user, typed, typed_runtime, phase)
    # Only htmx swaps the card in place; a plain post is answered with the page (#88).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    # A save closes the card, which lists the note now and shows the runtime; a refusal keeps it open with both boxes as typed (#132, #133).
    if not refusals:
        card = pool.the_card(suggestion, request.user, phase)
        return render(request, "components/film_card.html", {"card": card, "expanded": False, "phase_bar": pool.PHASE_BARS[phase]})
    box = card.note_box
    if isinstance(refusals.note, notes.TooLong):
        box = replace(box, text=typed, was=box.text, refusal=notes.too_long(refusals.note, box.is_pitch))
    elif refusals.note is not None:
        box = replace(box, refusal=notes.PITCH_REQUIRED)
    else:
        box = replace(box, text=typed, was=box.text)
    pencil = card.runtime_pencil
    # The box stays open as typed only where the runtime part acts; a film approved since has lost its pencil (#133).
    if pencil is not None and saving.runtime_acts(suggestion, typed_runtime, phase):
        pencil = replace(pencil, open=True, typed=typed_runtime, refusal=refusals.runtime)
    context = {"card": replace(card, note_box=box, runtime_pencil=pencil), "expanded": True, "phase_bar": pool.PHASE_BARS[phase]}
    return render(request, "components/film_card.html", context)


@require_safe
def dtdd_topics(request):
    """A card's full DoesTheDogDie topic list, a read in every phase but RUN, fetched as the list first opens; the same for every viewer (#103)."""
    # Only htmx fetches the list in; a plain GET is a click from before htmx loaded (#89).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    # A card withdrawn since reloads the tab onto the pool as it is now (#89); RUN shows no trigger data anywhere (#106).
    if (suggestion := named_suggestion(request.GET.get("suggestion"))) is None or current() == Phase.RUN:
        return reload_the_tab(request, reverse("phase_page"))
    return render(request, "components/dtdd_topics.html", {"dtdd": replace(stored.section_of(suggestion), watch=offered_watch(request.user, suggestion))})


def offered_watch(voter, suggestion):
    """The watch toggles for a voter's card, or None while *I don't care* is on; the admin's card never asks, as it has no list (#35 §2, #110, #114)."""
    if watched.does_not_care(voter):
        return None
    return Watch(at=reverse("dtdd_watch"), suggestion_id=suggestion.pk, ticked=frozenset(watched.ticked_ids(voter)))


@phase_window(*WRITING)
@require_POST
def watch_from_card(request):
    """Watch or unwatch one topic from a card's list: the page's own write, answered with the card's section, open, and the ring (#107, #114)."""
    if (posted := posted_tick(request)) is None:
        return HttpResponseBadRequest()
    # A card withdrawn since, or *I don't care* turned on elsewhere, changes nothing and reloads the tab onto the phase page as it is now (#89, #110).
    if (suggestion := named_suggestion(request.POST.get("suggestion"))) is None or not watched.set_ticked(request.user, *posted):
        return reload_the_tab(request, reverse("phase_page"))
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    card = pool.the_card(suggestion, request.user, current())
    opened = replace(card.dtdd, topics_at="", opened=True, watch=offered_watch(request.user, suggestion))
    # The match line's control keeps whatever it holds; the poster's ring follows the list out of band (#111).
    return dtdd_section(request, replace(card, dtdd=opened), ring_too=True, answers_the_control=False)


# Any voter, on any film; VOTE's card is M6's, and the admin's correction is never gated (#32 §5, #78, #105).
CORRECTING = (Phase.SUGGEST, Phase.APPROVE, Phase.VOTE)


@phase_window(*CORRECTING)
def correct_match(request):
    """Correct a match: a GET previews the record a pasted link names, or cancels, writing nothing, and Use this match's POST saves it (#105)."""
    if request.method == "POST":
        return use_match(request)
    return preview_match(request)


def preview_match(request):
    # Only htmx swaps the section in place; a plain GET is a click from before htmx loaded (#89).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    suggestion = named_suggestion(request.GET.get("suggestion"))
    # A tab left open past VOTE, or a card withdrawn since, reloads onto the phase page as it is now (#78, #92).
    if suggestion is None or (phase := current()) not in CORRECTING:
        return reload_the_tab(request, reverse("phase_page"))
    card = pool.the_card(suggestion, request.user, phase)
    if "cancel" not in request.GET:
        card = replace(card, dtdd=correction.previewed(card.dtdd, suggestion, request.GET.get("link", "")))
    return dtdd_section(request, card)


def use_match(request):
    if (suggestion := named_suggestion(request.POST.get("suggestion"))) is None:
        return reload_the_tab(request, reverse("phase_page"))
    try:
        correction.use(suggestion, request.POST.get("snapshot", ""), request.user.display_name)
    except correction.Tampered:
        return HttpResponseBadRequest()
    # Only htmx swaps the section in place; a plain post is answered with the page (#88).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    # The poster's ring follows the new record, so it travels out of band with the section (#111).
    return dtdd_section(request, pool.the_card(suggestion, request.user, current()), ring_too=True)


def dtdd_section(request, card, ring_too=False, answers_the_control=True):
    context = {"card": card, "dtdd": card.dtdd, "answers_the_control": answers_the_control, "oob": True}
    answer = render(request, "components/dtdd_section.html", context)
    if ring_too:
        answer.content += render(request, "components/film_card_poster.html", context).content
    return answer


@phase_window(Phase.SUGGEST)
def withdraw(request):
    """Withdraw on your own card: a GET arms it or cancels, writing nothing, and the confirm's POST withdraws (#85, #89)."""
    if request.method == "POST":
        return confirm_withdraw(request)
    return arm_withdraw(request)


def arm_withdraw(request):
    # Only htmx swaps the act in place; a plain GET is a click from before htmx loaded (#89).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    suggestion = named_suggestion(request.GET.get("suggestion"))
    # A tab left open past SUGGEST, or a card withdrawn since, reloads onto the phase page as it is now (#78, #88).
    if suggestion is None or current() is not Phase.SUGGEST:
        return reload_the_tab(request, reverse("phase_page"))
    card = pool.the_card(suggestion, request.user, Phase.SUGGEST)
    # Not the viewer's to withdraw, or approved since: the act leaves the card, with no explanation (#27).
    if card.withdraw is None:
        return HttpResponse()
    act = replace(card.withdraw, armed="cancel" not in request.GET)
    return render(request, "components/withdraw.html", {"card": replace(card, withdraw=act)})


def confirm_withdraw(request):
    # The confirm names its suggestion, so a second one, or one for a suggestion gone, finds nothing to take (#89).
    suggestion = named_suggestion(request.POST.get("suggestion"))
    if suggestion is not None and withdrawal.may_withdraw(request.user, suggestion):
        withdrawal.withdraw(suggestion)
        suggestion = None
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    # Gone: the empty answer swaps the card out of the pool, in place.
    if suggestion is None:
        return HttpResponse()
    # Refused: the card as it is now, which offers no withdraw (#27).
    card = pool.the_card(suggestion, request.user, Phase.SUGGEST)
    context = {"card": card, "expanded": True, "phase_bar": pool.PHASE_BARS[Phase.SUGGEST]}
    return render(request, "components/film_card.html", context)


@require_safe
def open_runtime(request):
    """The runtime pencil, any voter's: a GET answers the card's runtime line with its box open, writing nothing; Save saves the box with the note (#89, #90, #133)."""
    # Only htmx opens the line in place; a plain GET is a click from before htmx loaded (#89).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    suggestion = named_suggestion(request.GET.get("suggestion"))
    # A tab left open past SUGGEST, or a card withdrawn since, reloads onto the phase page as it is now (#78, #89).
    if suggestion is None or current() is not Phase.SUGGEST:
        return reload_the_tab(request, reverse("phase_page"))
    card = pool.the_card(suggestion, request.user, Phase.SUGGEST)
    # Only the line is swapped, so a note being typed on the same card is left alone (#90).
    # Approved since: the line comes back without its pencil, with no explanation (#27).
    if card.runtime_pencil is not None:
        card = replace(card, runtime_pencil=replace(card.runtime_pencil, open=True))
    return render(request, "components/runtime.html", {"card": card})


@require_safe
def find(request):
    """Find, a read: the picker for what was typed, swapped in under the box by htmx in SUGGEST (#21, #78, #92)."""
    # Only htmx swaps the picker in; a plain GET is a search from before htmx loaded (#89).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    # A tab left open past SUGGEST reloads onto the phase page as it is now (#78).
    if current() is not Phase.SUGGEST:
        return reload_the_tab(request, reverse("phase_page"))
    return render(request, "components/picker.html", {"picker": picker.the_picker(request.GET.get("q", ""), tmdb_client(), request.user)})


@phase_window(Phase.SUGGEST, Phase.APPROVE)
def suggest(request):
    """The pitch step: a GET from a picker tile fetches the film and shows the step, writing nothing, and Add's POST suggests it; a film by hand has its own step (#21, #93, #94).

    Suggesting is only offered in SUGGEST; APPROVE's window just catches a tab left open (#34).
    """
    if request.method == "POST":
        return add(request)
    return pitch_step(request)


def pitch_step(request):
    # Only htmx swaps the step in; a plain GET is a click from before htmx loaded (#89).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    # A tab left open past SUGGEST reloads onto the phase page as it is now (#78, #92).
    if current() is not Phase.SUGGEST:
        return reload_the_tab(request, reverse("phase_page"))
    if "by_hand" in request.GET:
        return render(request, "suggestions/hand_step.html", {"step": hand_step_from(request.GET.get("q", ""))})
    try:
        tmdb_id = int(request.GET.get("tmdb_id", ""))
    except ValueError:
        return HttpResponseBadRequest()
    if tmdb_id <= 0:
        return HttpResponseBadRequest()
    # The film's one detail fetch, here and never inside Add's write lock, and never refreshed (#5, #26, #78).
    try:
        film = tmdb_client().film(tmdb_id)
    except NotAnswering:
        return render(request, "components/picker.html", {"picker": Picker(searched=True, outage=True)})
    return render(request, "suggestions/pitch_step.html", {"step": pitch.PitchStep(film, signed.signed(film))})


def hand_step_from(searched):
    # The boxes start from what was searched, a trailing year in its own box (the dev, 2026-10-23; #94).
    query = find_text.parsed(searched)
    return pitch.HandStep(hand_entered("", None, None), title=query.title, year="" if query.year is None else str(query.year))


def add_by_hand(request):
    typed = {name: request.POST.get(name, "") for name in ("title", "year", "pitch", "runtime")}
    try:
        pitch.add_by_hand(request.user, typed["title"], typed["year"], typed["pitch"], typed["runtime"])
    except pitch.Refused as refused:
        # Only htmx shows the step again; a plain post is answered with the page (#88).
        if request.headers.get("HX-Request") != "true":
            return redirect("phase_page")
        step = pitch.HandStep(
            hand_entered("", None, None),
            pitch=typed["pitch"],
            typed_runtime=typed["runtime"],
            pitch_refusal=refused.pitch,
            runtime_refusal=refused.runtime,
            title=typed["title"],
            year=typed["year"],
            title_refusal=refused.title,
            year_refusal=refused.year,
        )
        return render(request, "suggestions/hand_step.html", {"step": step})
    return reload_the_tab(request, reverse("phase_page"))


def add(request):
    if "by_hand" in request.POST:
        return add_by_hand(request)
    try:
        film = signed.unsigned(request.POST.get("film", ""))
    except signed.Tampered:
        return HttpResponseBadRequest()
    typed_pitch, typed_runtime = request.POST.get("pitch", ""), request.POST.get("runtime", "")
    try:
        pitch.add(request.user, film, typed_pitch, typed_runtime)
    except pitch.AlreadySuggested as already:
        # No second suggestion: the voter lands on the film's card, opened, with what they typed in its box (#26 §3).
        pool.keep_for_its_card(request.session, already.suggestion, typed_pitch)
    except pitch.Refused as refused:
        # Only htmx shows the step again; a plain post is answered with the page (#88).
        if request.headers.get("HX-Request") != "true":
            return redirect("phase_page")
        step = pitch.PitchStep(
            film,
            request.POST["film"],
            pitch=typed_pitch,
            typed_runtime=typed_runtime,
            pitch_refusal=refused.pitch,
            runtime_refusal=refused.runtime,
        )
        return render(request, "suggestions/pitch_step.html", {"step": step})
    # Back at the pool, where the new card is on top (#21).
    return reload_the_tab(request, reverse("phase_page"))
