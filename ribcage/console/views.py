from contextlib import suppress

from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from ribcage.console.moves import offered
from ribcage.console.roster import what_goes
from ribcage.identity.admin_session import admin_required
from ribcage.identity.models import Voter
from ribcage.identity.removal import remove
from ribcage.identity.reset import replacing, reset
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


def named_voter(pk):
    """The voter a form or a link names by id, or None for an id that names nobody, or no id at all."""
    try:
        return Voter.objects.filter(pk=pk).first()
    except (TypeError, ValueError):
        return None


def roster(request, context):
    return render_tab(request, "console/roster.html", {"voters": Voter.objects.order_by("display_name_key"), "tab": "console_roster", **context})


def armed_reset(voter, used=False):
    return {"armed": voter, "arming": "reset", "replacing": replacing(voter), "used": used}


@admin_required
def roster_tab(request):
    # Arming is a plain GET that changes nothing, naming the voter by id; a row arms one act at a time (#28, #79, #80).
    if armed := named_voter(request.GET.get("remove")):
        return roster(request, {"armed": armed, "arming": "remove", "goes": what_goes(armed)})
    if armed := named_voter(request.GET.get("reset")):
        return roster(request, armed_reset(armed))
    return roster(request, {})


@admin_required
@require_POST
def remove_voter(request):
    # A confirm for a voter already removed, or for nobody, removes nobody and reloads the tab (#79).
    if voter := named_voter(request.POST.get("voter")):
        remove(voter)
    return redirect("console_roster")


@admin_required
@require_POST
@never_cache
def reset_password(request):
    # The password is in this response alone, never a redirect's target, so no reload or address can show it again (#80).
    voter = named_voter(request.POST.get("voter"))
    password = voter and reset(voter, request.POST.get("replacing"))
    if password:
        return roster(request, {"was_reset": voter, "password": password})
    # Re-read, as the view's copy may predate the reset that refused this confirm, and its digest would be the one just used (#80).
    if voter and (voter := named_voter(voter.pk)):
        # A confirm out of date (a double click, a reload's resubmit) is refused, so say so and offer a fresh one (#80).
        return roster(request, armed_reset(voter, used=True))
    return redirect("console_roster")
