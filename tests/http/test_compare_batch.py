"""The batch's first proposal on Compare: solved on every render, in every phase, with its banner's endings (#17, #24, #165)."""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.ballot.models import BallotRecord
from ribcage.phase.order import PHASES
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box, Timetable
from tests.http.test_phase import walk_to
from tests.http.test_pick_plan import text

COMPARE = "/console/pick/compare/"


def batch(page):
    return re.search(r'<tbody class="slate-ledger__section" aria-label="This batch">(.*?)</tbody>', page, re.S)[1]


def cells(section):
    row = re.search(r'<tr class="slate-row" data-slate-row>(.*?)</tr>', section, re.S)[1]
    return {name: text(re.search(rf'<td[^>]*class="[^"]*{name}[^"]*"[^>]*>(.*?)</td>', row, re.S)[1]) for name in ("label", "floor", "sigma", "films")}


def film(title, runtime, approval=Approval.APPROVED):
    return Suggestion.objects.create(title=title, suggester_name="x", approval=approval, runtime=runtime)


@pytest.fixture
def votes(voters):
    """Cube (90) and The Thing (109) in a 9 hour budget: ada loves Cube, Dani's best is The Thing and he vetoed Cube, Hanna has no ballot."""
    Timetable.objects.create(pk=1, budget=540)
    cube, thing = film("Cube", 90), film("The Thing", 109)
    for voter, one, score, vetoed in [("ada", cube, 3, False), ("ada", thing, 1, False), ("Dani", thing, 2, False), ("Dani", cube, None, True)]:
        BallotRecord.objects.create(voter=voters[voter], suggestion=one, score=score, vetoed=vetoed)
    return {"cube": cube, "thing": thing, "voters": voters}


@pytest.mark.parametrize("phase", PHASES)
def test_compare_shows_proposal_1_with_its_banner_in_every_phase(admin, votes, phase):
    walk_to(phase)

    section = batch(admin.get(COMPARE).text)

    assert cells(section)["label"].startswith("Proposal 1")
    assert (cells(section)["films"], cells(section)["floor"], cells(section)["sigma"]) == ("2 · 3h19m", "2 =", "5 =")
    banner = text(re.search(r"<div class=\"batch-banner\".*?</div>", section, re.S)[0])
    assert "Floor computed over 2 of 3 — Hanna: no ballot" in banner
    assert re.search(r"no knobs · solved in \d+ ms", banner)
    assert "batch-banner__ending" not in section


def test_the_floor_set_line_sits_in_the_banner_and_not_above_the_ledger(admin, votes):
    page = admin.get(COMPARE).text
    compare = re.search(r'<section class="compare".*?</section>', page, re.S)[0]

    assert compare.count("data-floor-set") == 1
    assert compare.index("data-floor-set") > compare.index("This batch")


def test_a_budget_shorter_than_every_film_gives_the_empty_slate_and_says_so(admin, votes):
    Timetable.objects.update(budget=60)

    section = batch(admin.get(COMPARE).text)

    row = cells(section)
    assert row["label"].startswith("Proposal 1 (empty slate)")
    assert (row["floor"], row["sigma"], row["films"][:1]) == ("no floor", "0 =", "0")
    assert "Nothing fits the budget, so the proposal is the empty slate." in text(section)


def test_no_budget_says_nothing(admin, votes):
    Timetable.objects.update(budget=None)

    section = batch(admin.get(COMPARE).text)

    assert cells(section)["films"].startswith("2 · 3h19m")
    assert "batch-banner__ending" not in section


def test_an_empty_floor_set_says_the_total_alone_is_optimised(admin, votes):
    BallotRecord.objects.all().delete()

    assert "Nobody is in the floor set, so the total alone is optimised." in text(batch(admin.get(COMPARE).text))


def test_a_dropped_film_on_the_plan_is_never_proposed(admin, votes):
    ripley = film("Ripley", 100, Approval.DROPPED)
    Box.objects.create(suggestion=ripley, start=0)
    BallotRecord.objects.create(voter=votes["voters"]["ada"], suggestion=ripley, score=3)
    BallotRecord.objects.create(voter=votes["voters"]["Dani"], suggestion=ripley, score=3)

    assert cells(batch(admin.get(COMPARE).text))["films"] == "2 · 3h19m"


def test_the_query_count_does_not_grow_with_the_ballot(admin, votes):
    def queries():
        with CaptureQueriesContext(connection) as captured:
            admin.get(COMPARE)
        return len(captured)

    admin.get(COMPARE)
    small = queries()
    for number in range(8):
        more = film(f"More {number}", 80)
        BallotRecord.objects.create(voter=votes["voters"]["ada"], suggestion=more, score=2)
        BallotRecord.objects.create(voter=votes["voters"]["Dani"], suggestion=more, vetoed=True)

    assert queries() == small
