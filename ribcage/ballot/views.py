from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ribcage.ballot import board, placing
from ribcage.phase.check import phase_window
from ribcage.phase.order import Phase
from ribcage.reload import reload_the_tab


@phase_window(Phase.VOTE)
@require_POST
def place(request):
    """One placement: the film named, put where the post says. A film that is no candidate now, or a target that is none, changes nothing and reloads the ballot as it is (#34, #78, #119)."""
    target = placing.target_of(request.POST.get("to"))
    try:
        suggestion = board.candidates().filter(pk=request.POST.get("suggestion")).first()
    except (TypeError, ValueError):
        suggestion = None
    if suggestion is None or target is None:
        return reload_the_tab(request, reverse("phase_page"))
    placing.place(request.user, suggestion, target)
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    return render(request, "ballot/counts.html", {"counts": board.counts_of(request.user), "oob": True})
