from dataclasses import replace

from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ribcage.phase.check import phase_window
from ribcage.phase.history import current
from ribcage.phase.order import Phase
from ribcage.reload import reload_the_tab
from ribcage.suggestions import notes, pool
from ribcage.suggestions.models import Suggestion

PITCH_REQUIRED = "A suggestion needs its pitch, so yours is back as it was. Change it however you like."


def too_long(refusal, is_pitch):
    kind = "pitch" if is_pitch else "note"
    return f"That's {refusal.length:,} characters, and a {kind} holds {refusal.cap:,}. Trim it a little and save again."


def named_suggestion(pk):
    """The suggestion a post names by id, or None for one withdrawn since, or no id at all (#88, #89)."""
    try:
        return Suggestion.objects.filter(pk=pk).first()
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
