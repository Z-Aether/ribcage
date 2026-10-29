"""The plan's set readouts on Compare, in every phase (#12, #15, #24, #147)."""

import html
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.ballot.models import BallotRecord
from ribcage.phase.order import PHASES
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box, Timetable
from tests.http.test_phase import walk_to

COMPARE = "/console/pick/compare/"
EMPTY = "Nothing on the timetable yet."


def text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def the_plan(page):
    return re.search(r'<section class="the-plan".*?</section>', page, re.S)[0]


def table(page):
    return {text(name): text(rest) for name, rest in re.findall(r'<td class="the-plan__voter">(.*?)</td>(.*?)</tr>', the_plan(page), re.S)}


def line(page):
    return text(re.search(r'<p class="the-plan__line">(.*?)</p>', the_plan(page), re.S)[1])


def put(title, runtime, approval=Approval.APPROVED, start=None, suggester=None):
    film = Suggestion.objects.create(title=title, suggester=suggester, suggester_name="x", approval=approval, runtime=runtime)
    if start is not None:
        Box.objects.create(suggestion=film, start=start)
    return film


@pytest.fixture
def plan(voters):
    """Cube and The Thing on the timetable (199 minutes) in a 9 hour budget: ada loves Cube, Dani's best is The Thing and he vetoed Cube, Hanna has no ballot."""
    Timetable.objects.create(pk=1, budget=540)
    cube, thing = put("Cube", 90, start=0, suggester=voters["ada"]), put("The Thing", 109, start=90, suggester=voters["ada"])
    for voter, film, score, vetoed in [("ada", cube, 3, False), ("ada", thing, 1, False), ("Dani", thing, 2, False), ("Dani", cube, None, True)]:
        BallotRecord.objects.create(voter=voters[voter], suggestion=film, score=score, vetoed=vetoed)
    return {"cube": cube, "thing": thing, "voters": voters}


@pytest.mark.parametrize("phase", PHASES)
def test_compare_reads_the_plan_in_every_phase_with_the_floor_pinner_starred(admin, plan, phase):
    walk_to(phase)

    page = admin.get(COMPARE).text

    assert line(page) == "2 films · 3h19m of 9h budget · floor 2 · Σrep 5"
    assert table(page) == {
        "ada": "Cube 3",
        "Dani ★": "The Thing 2",
        "Hanna": "no ballot",
    }
    assert text(re.search(r'<p class="the-plan__vetoed">(.*?)</p>', page, re.S)[1]) == "Vetoed: Cube (Dani)"
    assert "Floor computed over 2 of 3 — Hanna: no ballot" in text(the_plan(page))


def test_the_line_says_over_past_the_budget_and_no_budget_without_one(admin, plan):
    Timetable.objects.update(budget=180)
    assert 'class="the-plan__over">over<' in admin.get(COMPARE).text
    assert line(admin.get(COMPARE).text) == "2 films · 3h19m of 3h budget over · floor 2 · Σrep 5"

    Timetable.objects.update(budget=None)
    assert line(admin.get(COMPARE).text) == "2 films · 3h19m, no budget · floor 2 · Σrep 5"
    assert "the-plan__over" not in admin.get(COMPARE).text


def test_removing_a_box_changes_the_readouts_and_moving_one_does_not(admin, plan):
    before = the_plan(admin.get(COMPARE).text)
    Box.objects.filter(suggestion=plan["cube"]).update(start=300)
    assert the_plan(admin.get(COMPARE).text) == before

    Box.objects.filter(suggestion=plan["cube"]).delete()
    page = admin.get(COMPARE).text

    assert line(page) == "1 film · 1h49m of 9h budget · floor 1 · Σrep 3"
    assert table(page)["ada ★"] == "The Thing 1"
    assert "Vetoed: none" in text(the_plan(page))


def test_moving_a_box_keeps_a_tie_s_representative_and_the_vetoed_order(admin, plan):
    alien = put("Alien", 117, start=200)
    for voter, film, score, vetoed in [("Hanna", plan["cube"], 2, False), ("Hanna", plan["thing"], 2, False), ("Hanna", alien, None, True)]:
        BallotRecord.objects.create(voter=plan["voters"][voter], suggestion=film, score=score, vetoed=vetoed)

    def read():
        page = admin.get(COMPARE).text
        return table(page), text(re.search(r'<p class="the-plan__vetoed">(.*?)</p>', page, re.S)[1])

    before = read()
    Box.objects.filter(suggestion=plan["cube"]).update(start=500)

    assert before[0]["Hanna ★"].startswith("The Thing 2") and before[1] == "Vetoed: Cube (Dani); Alien (Hanna)"
    assert read() == before


def test_a_dropped_film_on_the_timetable_still_represents_and_an_empty_floor_set_has_no_floor(admin, plan):
    Suggestion.objects.filter(pk=plan["cube"].pk).update(approval=Approval.DROPPED)
    page = admin.get(COMPARE).text

    assert table(page)["ada"] == "Cube 3"

    BallotRecord.objects.all().delete()
    assert " no floor " in line(admin.get(COMPARE).text) + " "


def test_a_timetable_with_no_boxes_says_so(admin, plan):
    Box.objects.all().delete()

    page = admin.get(COMPARE).text

    assert EMPTY in the_plan(page)
    assert "the-plan__table" not in page


def test_a_labelled_box_alone_is_a_plan_with_no_films(admin, voters):
    Box.objects.create(label="Dinner", length=45, start=0)

    assert line(admin.get(COMPARE).text) == "0 films · 0m, no budget · no floor · Σrep 0"


def test_the_query_count_does_not_grow_with_the_slate(admin, plan):
    def queries():
        with CaptureQueriesContext(connection) as captured:
            admin.get(COMPARE)
        return len(captured)

    admin.get(COMPARE)
    small = queries()
    for number in range(6):
        film = put(f"Film {number}", 80, start=300 + 100 * number)
        BallotRecord.objects.create(voter=plan["voters"]["ada"], suggestion=film, score=2)
        BallotRecord.objects.create(voter=plan["voters"]["Dani"], suggestion=film, vetoed=True)

    assert queries() == small
