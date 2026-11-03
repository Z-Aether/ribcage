from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_safe

from ribcage.ballot import board, done, reopened, reveal
from ribcage.phase.check import reload_into_the_current_phase
from ribcage.phase.history import current, reveal_has_happened
from ribcage.phase.order import Phase
from ribcage.suggestions import pool
from ribcage.timetable import evening

PHASE_PAGES = {
    Phase.SUGGEST: "phase/suggest.html",
    Phase.APPROVE: "phase/approve.html",
    Phase.VOTE: "phase/vote.html",
    Phase.PICK: "phase/pick.html",
    Phase.RUN: "phase/run.html",
}


def the_pool(request, phase):
    cards, opened = pool.kept_for_its_card(pool.film_cards(request.user, phase), request.session)
    return {"pool": cards, "phase_bar": pool.PHASE_BARS[phase], "opened": opened}


def the_ballot(request, phase):
    return {"board": board.of(request.user, places_at=reverse("ballot_place")), "roster": done.roster(request.user), "done_at": reverse("ballot_done"), "reopened": reopened.LINE if reveal_has_happened() else None}


def the_reveal(request, phase):
    return {"reveal": reveal.load(request.user, request.GET.get("sort", ""))}


def the_evening(request, phase):
    return {"evening": evening.load(), "poll_seconds": settings.POLL_INTERVAL_SECONDS, "header_page": "evening"}


# Voters read the pool in SUGGEST and APPROVE only; in VOTE the ballot takes its place (#27, #119).
PHASE_CONTEXTS = {
    Phase.SUGGEST: the_pool,
    Phase.APPROVE: the_pool,
    Phase.VOTE: the_ballot,
    Phase.PICK: the_reveal,
    Phase.RUN: the_evening,
}


@require_safe
def phase_page(request):
    # The page is the phase: / shows the current phase's page and nothing else (#27).
    phase = current()
    context = PHASE_CONTEXTS[phase](request, phase) if phase in PHASE_CONTEXTS else {}
    return render(request, PHASE_PAGES[phase], context)


@require_safe
def evening_poll(request):
    """The evening as it stands, which the page swaps in place every POLL_INTERVAL_SECONDS: a plain GET, since a post that the CSRF check refuses reloads the tab (#13, #76, #160).

    Outside RUN, and outside htmx, the whole tab reloads into the current phase, so RUN to PICK takes the evening down and keeps no last published one (#36).
    """
    if current() is not Phase.RUN or request.headers.get("HX-Request") != "true":
        return reload_into_the_current_phase(request)
    return render(request, "components/evening.html", the_evening(request, Phase.RUN))


@require_safe
def reveal_page(request):
    """The reveal at an address of its own, for RUN, where `/` is the evening: in PICK `/` is the reveal, and anywhere else the tab reloads into the phase so no score shows outside it (#8, #34, #161).

    A GET, which the phase check leaves to the view. The page does not poll (#60).
    """
    phase = current()
    if phase is Phase.PICK:
        return redirect("phase_page")
    if phase is not Phase.RUN:
        return reload_into_the_current_phase(request)
    return render(request, "phase/reveal.html", {"reveal": reveal.load(request.user, request.GET.get("sort", "")), "header_page": "reveal"})


# The stretch of the marathon each phase belongs to, and the button under its entry, naming what the voter does there (#75, #134).
HOW_IT_WORKS_NOW = {
    Phase.SUGGEST: ("suggest", "Suggest films"),
    Phase.APPROVE: ("suggest", "See the suggestions"),
    Phase.VOTE: ("vote", "Vote"),
    Phase.PICK: ("evening", "See the scores"),
    Phase.RUN: ("evening", "Follow the evening"),
}


@require_safe
def how_it_works(request):
    phase = current()
    now, button = HOW_IT_WORKS_NOW[phase]
    return render(request, "phase/how_it_works.html", {"now": now, "button": button, "warnings_button": phase is not Phase.RUN})
