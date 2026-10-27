from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_safe

from ribcage.ballot import board, done, reopened
from ribcage.phase.history import current, reveal_has_happened
from ribcage.phase.order import Phase
from ribcage.suggestions import pool

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


# Voters read the pool in SUGGEST and APPROVE only; in VOTE the ballot takes its place (#27, #119).
PHASE_CONTEXTS = {
    Phase.SUGGEST: the_pool,
    Phase.APPROVE: the_pool,
    Phase.VOTE: the_ballot,
}


@require_safe
def phase_page(request):
    # The page is the phase: / shows the current phase's page and nothing else (#27).
    phase = current()
    context = PHASE_CONTEXTS[phase](request, phase) if phase in PHASE_CONTEXTS else {}
    return render(request, PHASE_PAGES[phase], context)


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
