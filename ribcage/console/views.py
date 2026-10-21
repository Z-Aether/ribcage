from django.shortcuts import redirect, render

from ribcage.identity.admin_session import admin_required
from ribcage.phase.history import current
from ribcage.phase.order import Phase

# Where each phase's work is: Films through VOTE, Pick from PICK on (#28).
WORKING_TABS = {
    Phase.SUGGEST: "console_films",
    Phase.APPROVE: "console_films",
    Phase.VOTE: "console_films",
    Phase.PICK: "console_pick",
    Phase.RUN: "console_pick",
}


@admin_required
def console(request):
    # Only the landing follows the phase; each tab keeps its own address, so it stays put when the phase moves (#28).
    return redirect(WORKING_TABS[current()])


@admin_required
def phase_tab(request):
    return render(request, "console/phase.html")


@admin_required
def films_tab(request):
    return render(request, "console/films.html")


@admin_required
def pick_tab(request):
    return render(request, "console/pick.html")


@admin_required
def roster_tab(request):
    return render(request, "console/roster.html")
