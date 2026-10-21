from contextlib import suppress

from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ribcage.console.moves import offered
from ribcage.identity.admin_session import admin_required
from ribcage.identity.models import Voter
from ribcage.phase.history import current, last_entered, move
from ribcage.phase.order import PHASES, MoveRefused, Phase

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
        "phases": [(phase, entered.get(phase)) for phase in PHASES],
        "moves": offered(phase, armed_to),
        "voters": Voter.objects.count(),
    }
    return render_tab(request, "console/phase.html", context, phase)


@admin_required
@require_POST
def move_phase(request):
    # The post names the phase it expects to leave, so a stale tab moves nothing and reloads into the phase as it is (#74, #77).
    with suppress(MoveRefused):
        move(request.POST.get("from_phase"), request.POST.get("to_phase"))
    return redirect("console_phase")


@admin_required
def films_tab(request):
    return render_tab(request, "console/films.html")


@admin_required
def pick_tab(request):
    return render_tab(request, "console/pick.html")


@admin_required
def roster_tab(request):
    return render_tab(request, "console/roster.html")
