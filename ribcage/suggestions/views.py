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
from ribcage.suggestions import notes, picker, pitch, pool, runtime, withdrawal
from ribcage.suggestions.models import Suggestion
from ribcage.triggers import correction, stored

def named_suggestion(pk):
    """The suggestion a post names by id, or None for one withdrawn since, or no id at all (#88, #89)."""
    try:
        return withdrawal.with_holds(Suggestion.objects.filter(pk=pk)).first()
    except (TypeError, ValueError):
        return None


@phase_window(Phase.SUGGEST, Phase.APPROVE)
@require_POST
def write_note(request):
    # The card the post came from is gone, so the tab reloads onto the pool as it is now (#89).
    if (suggestion := named_suggestion(request.POST.get("suggestion"))) is None:
        return reload_the_tab(request, reverse("phase_page"))
    typed = request.POST.get("text", "")
    phase = current()
    card = pool.the_card(suggestion, request.user, phase)
    try:
        notes.write(suggestion, request.user, typed)
    except notes.TooLong as refusal:
        box = replace(card.note_box, text=typed, refusal=notes.too_long(refusal, card.note_box.is_pitch))
    except notes.PitchRequired:
        box = replace(card.note_box, refusal=notes.PITCH_REQUIRED)
    else:
        card = pool.the_card(suggestion, request.user, phase)
        box = replace(card.note_box, saved=True)
    # Only htmx swaps the card in place; a plain post is answered with the page (#88).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    context = {"card": replace(card, note_box=box), "expanded": True, "phase_bar": pool.PHASE_BARS[phase]}
    return render(request, "components/film_card.html", context)


@require_safe
def dtdd_topics(request):
    """A card's full DoesTheDogDie topic list, a read in any phase, fetched as the list first opens; the same for every viewer (#103)."""
    # Only htmx fetches the list in; a plain GET is a click from before htmx loaded (#89).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    # A card withdrawn since reloads the tab onto the pool as it is now (#89).
    if (suggestion := named_suggestion(request.GET.get("suggestion"))) is None:
        return reload_the_tab(request, reverse("phase_page"))
    return render(request, "components/dtdd_topics.html", {"dtdd": stored.section_of(suggestion)})


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
    return dtdd_section(request, pool.the_card(suggestion, request.user, current()))


def dtdd_section(request, card):
    return render(request, "components/dtdd_section.html", {"card": card, "dtdd": card.dtdd, "answers_the_control": True})


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


@phase_window(Phase.SUGGEST)
def correct_runtime(request):
    """The runtime pencil, any voter's: a GET opens the runtime line or closes it, writing nothing, and its POST saves (#89, #90)."""
    if request.method == "POST":
        return save_runtime(request)
    return open_runtime(request)


def runtime_line(request, card):
    # Only the line is swapped, so a note being typed on the same card is left alone (#90).
    return render(request, "components/runtime.html", {"card": card})


def open_runtime(request):
    # Only htmx opens the line in place; a plain GET is a click from before htmx loaded (#89).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    suggestion = named_suggestion(request.GET.get("suggestion"))
    # A tab left open past SUGGEST, or a card withdrawn since, reloads onto the phase page as it is now (#78, #89).
    if suggestion is None or current() is not Phase.SUGGEST:
        return reload_the_tab(request, reverse("phase_page"))
    card = pool.the_card(suggestion, request.user, Phase.SUGGEST)
    # Approved since: the line comes back without its pencil, with no explanation (#27).
    if card.runtime_pencil is not None:
        card = replace(card, runtime_pencil=replace(card.runtime_pencil, open="cancel" not in request.GET))
    return runtime_line(request, card)


def save_runtime(request):
    if (suggestion := named_suggestion(request.POST.get("suggestion"))) is None:
        return reload_the_tab(request, reverse("phase_page"))
    typed = request.POST.get("runtime", "")
    refusal = ""
    # Approved since: nothing is written, and the line comes back as it is now, without its pencil (#34).
    if withdrawal.withdrawable(suggestion):
        try:
            runtime.correct(suggestion, typed)
        except runtime.Refused as refused:
            refusal = str(refused)
    # Only htmx swaps the line in place; a plain post is answered with the page (#88).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    card = pool.the_card(suggestion, request.user, Phase.SUGGEST)
    if refusal:
        card = replace(card, runtime_pencil=replace(card.runtime_pencil, open=True, typed=typed, refusal=refusal))
    return runtime_line(request, card)


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
