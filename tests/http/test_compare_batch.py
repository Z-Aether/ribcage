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


def settings_default():
    from ribcage.readouts import tiebreaker

    return tiebreaker.DEFAULT


def batch(page):
    return re.search(r'<tbody class="slate-ledger__section" aria-label="This batch">(.*?)</tbody>', page, re.S)[1]


def cells(section):
    row = re.search(r'<tr class="slate-row" data-slate-row>(.*?)</tr>', section, re.S)[1]
    return {name: text(re.search(rf'<td[^>]*class="[^"]*{name}[^"]*"[^>]*>(.*?)</td>', row, re.S)[1]) for name in ("label", "floor", "sigma", "total", "films")}


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


@pytest.mark.parametrize("rule", ["total", "leximin"])
def test_an_empty_floor_set_says_the_tiebreaker_alone_is_optimised(admin, votes, settings, rule):
    settings.SLATE_TIEBREAKER = rule
    BallotRecord.objects.all().delete()

    assert f"Nobody is in the floor set, so the tiebreaker ({rule}) alone is optimised." in text(batch(admin.get(COMPARE).text))


def test_with_the_setting_unset_the_default_rule_is_leximin():
    assert settings_default() == "leximin"


@pytest.mark.parametrize("rule", ["total", "leximin"])
def test_compare_renders_the_batch_and_every_row_under_each_rule(admin, votes, settings, rule):
    settings.SLATE_TIEBREAKER = rule
    Box.objects.create(suggestion=votes["thing"], start=0)

    response = admin.get(COMPARE)

    assert response.status_code == 200
    page = response.text
    assert cells(batch(page))["label"].startswith("Proposal 1")
    assert cells(batch(page))["films"] == "2 · 3h19m"
    assert re.search(r'<th scope="col" class="ledger__number" data-tiebreaker>(Total|Leximin)</th>', page)[1] == rule.capitalize()
    assert re.findall(r'<td class="ledger__number slate-row__total">\d+ <small class="slate-row__distance">(.*?)</small>', page)


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
    admin.get(COMPARE)  # the changed ballot is kept by this render, which writes the session once

    assert queries() == small


@pytest.fixture
def many(voters, settings):
    """Six approved films of 100 minutes in a 4 hour budget, scored by ada and Dani, cut by 2 and a batch of 3."""
    settings.DIVERSITY_CUT, settings.BATCH_SIZE = 2, 3
    Timetable.objects.create(pk=1, budget=240)
    for number in range(6):
        one = film(f"Film {number}", 100)
        for voter, score in [("ada", number % 4), ("Dani", (number * 2) % 4)]:
            BallotRecord.objects.create(voter=voters[voter], suggestion=one, score=score)


def proposals(page):
    return re.findall(r'class="slate-row__opens"[^>]*>\s*(Proposal \d+)', page)


def heading(page):
    return text(re.search(r'aria-label="This batch">\s*<tr class="slate-ledger__heading">(.*?)</tr>', page, re.S)[1])


def test_compare_shows_batch_size_proposals_with_the_count_and_more_in_the_header(admin, many):
    page = admin.get(COMPARE).text

    assert proposals(page) == ["Proposal 1", "Proposal 2", "Proposal 3"]
    assert heading(page) == "This batch 3 · more"
    assert "data-batch-more" in page and not re.search(r"<button[^>]*disabled[^>]*data-batch-more", page)


def test_the_total_is_a_column_after_sigma_rep_with_its_distance_from_the_best_row(admin, many, settings):
    settings.SLATE_TIEBREAKER = "total"
    page = admin.get(COMPARE).text
    head = re.search(r"<thead>(.*?)</thead>", page, re.S)[1]
    row = re.search(r'<tr class="slate-row" data-slate-row>(.*?)</tr>', page, re.S)[1]

    assert re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)[3:5] == ["Σrep", "Total"]
    found = re.findall(r'<td class="ledger__number slate-row__total">(\d+) <small class="slate-row__distance">(=|[−+]\d+)</small>', page)
    shown = [(int(total), 0 if said == "=" else int(said.replace("−", "-"))) for total, said in found]
    assert len(shown) >= 3 and len({total for total, _ in shown}) > 1  # rows whose totals differ
    assert len({total - distance for total, distance in shown}) == 1  # every distance is from one best total
    assert re.search(r'<th scope="rowgroup" colspan="%d"' % len(re.findall(r"<th", head)), page)  # the heading spans every column


def test_a_short_batch_says_why_and_greys_more(admin, votes, settings):
    settings.DIVERSITY_CUT = 4

    page = admin.get(COMPARE).text

    assert proposals(page) == ["Proposal 1"]
    assert heading(page) == "This batch 1 · more No other slate differs from these by 4 or more films."
    assert re.search(r"<button[^>]*disabled[^>]*data-batch-more", page)


def test_more_extends_the_batch_in_the_admins_session_and_keeps_the_first(admin, many):
    before = proposals(admin.get(COMPARE).text)
    first = cells(batch(admin.get(COMPARE).text))["films"]

    assert admin.post("/console/pick/more/").status_code == 302
    page = admin.get(COMPARE).text

    assert proposals(page)[:3] == before and len(proposals(page)) == 6
    assert cells(batch(page))["films"] == first
    assert heading(page).startswith("This batch 6")


def test_more_until_the_chain_ends_greys_it_with_the_reason(admin, many):
    for _ in range(6):
        admin.post("/console/pick/more/")

    page = admin.get(COMPARE).text

    assert len(proposals(page)) < 3 * 7
    assert "No other slate differs from these by 2 or more films." in heading(page)


def test_saving_the_budget_resets_more_to_one_batch(admin, many):
    admin.post("/console/pick/more/")
    assert len(proposals(admin.get(COMPARE).text)) == 6

    admin.post("/console/pick/budget/", {"hours": "5", "minutes": "0", "sub": "compare"})

    assert len(proposals(admin.get(COMPARE).text)) == 3


def test_a_refused_budget_keeps_more(admin, many):
    admin.post("/console/pick/more/")

    admin.post("/console/pick/budget/", {"hours": "x", "minutes": "", "sub": "compare"})

    assert len(proposals(admin.get(COMPARE).text)) == 6


def test_the_same_votes_give_the_same_batch_on_every_render(admin, many):
    def films(page):
        return [text(each) for each in re.findall(r'<td[^>]*class="[^"]*films[^"]*"[^>]*>(.*?)</td>', batch(page), re.S)]

    assert films(admin.get(COMPARE).text) == films(admin.get(COMPARE).text)


def test_the_query_count_does_not_grow_with_the_batch(admin, many):
    def queries():
        with CaptureQueriesContext(connection) as captured:
            admin.get(COMPARE)
        return len(captured)

    admin.get(COMPARE)
    one = queries()
    admin.post("/console/pick/more/")
    admin.get(COMPARE)

    assert queries() == one


@pytest.fixture
def solves(monkeypatch):
    """The number of times a render calls the solver, counted from now."""
    from ribcage.solver.model import solve

    calls = []
    monkeypatch.setattr("ribcage.timetable.batch.solve", lambda *args, **kwargs: calls.append(1) or solve(*args, **kwargs))
    return calls


def test_a_render_after_more_solves_only_the_new_proposals(admin, many, solves, settings):
    admin.get(COMPARE)
    assert len(solves) == settings.BATCH_SIZE
    solves.clear()

    admin.post("/console/pick/more/")
    page = admin.get(COMPARE).text

    assert len(solves) == settings.BATCH_SIZE and len(proposals(page)) == 6
    assert re.search(r"solved in \d+ ms", page)


def test_a_repeat_render_with_nothing_new_solves_nothing(admin, many, solves):
    admin.post("/console/pick/more/")
    first = admin.get(COMPARE).text
    solves.clear()

    again = admin.get(COMPARE).text
    admin.get(COMPARE)

    assert solves == []
    assert proposals(again) == proposals(first) and "nothing new to solve" in again


def test_a_chain_the_cut_ended_is_not_solved_again(admin, many, solves):
    for _ in range(6):
        admin.post("/console/pick/more/")
    admin.get(COMPARE)
    solves.clear()

    page = admin.get(COMPARE).text

    assert solves == [] and "No other slate differs" in heading(page)


def test_a_vote_changed_between_renders_resets_more_and_solves_again(admin, many, voters, solves, settings):
    admin.post("/console/pick/more/")
    assert len(proposals(admin.get(COMPARE).text)) == 6
    solves.clear()
    one = Suggestion.objects.get(title="Film 0")
    BallotRecord.objects.update_or_create(voter=voters["ada"], suggestion=one, defaults={"score": 3, "vetoed": False})
    BallotRecord.objects.filter(voter=voters["Dani"], suggestion=one).update(score=-1)

    page = admin.get(COMPARE).text

    assert len(proposals(page)) == 3 and len(solves) == settings.BATCH_SIZE
    assert len(proposals(admin.get(COMPARE).text)) == 3


def test_a_film_added_to_the_ballot_between_renders_resets_more(admin, many, voters, solves):
    admin.post("/console/pick/more/")
    assert len(proposals(admin.get(COMPARE).text)) == 6
    extra = film("Extra", 90)
    BallotRecord.objects.create(voter=voters["ada"], suggestion=extra, score=3)

    assert len(proposals(admin.get(COMPARE).text)) == 3

