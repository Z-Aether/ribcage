from dataclasses import replace

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ribcage.phase.check import phase_window
from ribcage.phase.history import current
from ribcage.phase.order import Phase
from ribcage.reload import reload_the_tab
from ribcage.suggestions import notes, pool, withdrawal
from ribcage.suggestions.models import Suggestion

PITCH_REQUIRED = "A suggestion needs its pitch, so yours is back as it was. Change it however you like."


def too_long(refusal, is_pitch):
    kind = "pitch" if is_pitch else "note"
    return f"That's {refusal.length:,} characters, and a {kind} holds {refusal.cap:,}. Trim it a little and save again."


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
    card = pool.the_card(suggestion, request.user)
    try:
        notes.write(suggestion, request.user, typed)
    except notes.TooLong as refusal:
        box = replace(card.note_box, text=typed, refusal=too_long(refusal, card.note_box.is_pitch))
    except notes.PitchRequired:
        box = replace(card.note_box, refusal=PITCH_REQUIRED)
    else:
        card = pool.the_card(suggestion, request.user)
        box = replace(card.note_box, saved=True)
    # Only htmx swaps the card in place; a plain post is answered with the page (#88).
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    context = {"card": replace(card, note_box=box), "expanded": True, "phase_bar": pool.PHASE_BARS[current()]}
    return render(request, "components/film_card.html", context)


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
    card = pool.the_card(suggestion, request.user)
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
    context = {"card": pool.the_card(suggestion, request.user), "expanded": True, "phase_bar": pool.PHASE_BARS[Phase.SUGGEST]}
    return render(request, "components/film_card.html", context)
