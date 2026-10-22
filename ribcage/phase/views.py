from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe

from ribcage.identity.views import WELCOME_PENDING
from ribcage.phase.history import current
from ribcage.phase.order import Phase

PHASE_PAGES = {
    Phase.SUGGEST: "phase/suggest.html",
    Phase.APPROVE: "phase/approve.html",
    Phase.VOTE: "phase/vote.html",
    Phase.PICK: "phase/pick.html",
    Phase.RUN: "phase/run.html",
}


@require_safe
def phase_page(request):
    # The page is the phase: / shows the current phase's page and nothing else (#27).
    return render(request, PHASE_PAGES[current()])


# Each phase's exit from Welcome, naming what the voter does there (#75).
WELCOME_EXITS = {
    Phase.SUGGEST: "Suggest films",
    Phase.APPROVE: "See the suggestions",
    Phase.VOTE: "Vote",
    Phase.PICK: "See the scores",
    Phase.RUN: "Follow the evening",
}


@require_safe
def welcome(request):
    # Anyone who arrives without having just registered goes to the phase page (#75).
    if not request.session.pop(WELCOME_PENDING, False):
        return redirect("phase_page")
    return render(request, "phase/welcome.html", {"exits": [(WELCOME_EXITS[current()], "phase_page")]})
