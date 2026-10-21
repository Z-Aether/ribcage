from django.shortcuts import render

from ribcage.phase.history import current
from ribcage.phase.order import Phase

PHASE_PAGES = {
    Phase.SUGGEST: "phase/suggest.html",
    Phase.APPROVE: "phase/approve.html",
    Phase.VOTE: "phase/vote.html",
    Phase.PICK: "phase/pick.html",
    Phase.RUN: "phase/run.html",
}


def phase_page(request):
    # The page is the phase: / shows the current phase's page and nothing else (#27).
    return render(request, PHASE_PAGES[current()])
