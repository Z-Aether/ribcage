from dataclasses import replace

from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ribcage.ballot import board, placing
from ribcage.phase.check import phase_window
from ribcage.phase.order import Phase
from ribcage.reload import reload_the_tab
from ribcage.suggestions import notes


def candidate(posted):
    try:
        return board.candidates().filter(pk=posted).first()
    except (TypeError, ValueError):
        return None


@phase_window(Phase.VOTE)
@require_POST
def place(request):
    """One placement: the film named, put where the post says. A film that is no candidate now, or a target that is none, changes nothing and reloads the ballot as it is (#34, #78, #119)."""
    target = placing.target_of(request.POST.get("to"))
    suggestion = candidate(request.POST.get("suggestion"))
    if suggestion is None or target is None:
        return reload_the_tab(request, reverse("phase_page"))
    placing.place(request.user, suggestion, target)
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    # The tile is drawn again where it landed, since the Veto band's row is not a band's tile (#120).
    context = {"counts": board.counts_of(request.user), "oob": True, "tile": board.one_tile(request.user, suggestion), "row": target == placing.VETO}
    return render(request, "ballot/counts.html", context)


SEEN_STATES = {"1": True, "0": False}


@phase_window(Phase.VOTE)
@require_POST
def seen(request):
    """Seen it set to the state the post names, and the film's tile or veto frame drawn again; a stale post reloads the ballot as it is (#10, #34, #78, #121)."""
    state = SEEN_STATES.get(request.POST.get("seen"))
    suggestion = candidate(request.POST.get("suggestion"))
    if suggestion is None or state is None:
        return reload_the_tab(request, reverse("phase_page"))
    vetoed = placing.mark_seen(request.user, suggestion, state)
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    return render(request, "ballot/seen.html", {"tile": board.one_tile(request.user, suggestion), "row": vetoed, "oob": True})


@phase_window(Phase.VOTE)
@require_POST
def veto_reason(request):
    """The reason on the voter's own veto, kept as a note is; a film they no longer veto reloads the ballot as it is (#10, #88, #120)."""
    suggestion = candidate(request.POST.get("suggestion"))
    if suggestion is None:
        return reload_the_tab(request, reverse("phase_page"))
    typed = request.POST.get("text", "")
    refusal = None
    try:
        kept = placing.give_reason(request.user, suggestion, typed)
    except notes.TooLong as too_long:
        kept, refusal = True, too_long
    if not kept:
        return reload_the_tab(request, reverse("phase_page"))
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    tile = board.one_tile(request.user, suggestion)
    if refusal:
        tile = replace(tile, reason=typed, said=notes.too_long(refusal, False), refused=True)
    else:
        tile = replace(tile, said="Saved." if tile.reason else "Cleared.")
    return render(request, "ballot/tile.html", {"tile": tile, "row": True})
