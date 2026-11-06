"""Compare reads the tiebreaker: slate sums in the strip, the rule's column, the objective line and the swap's row (#177)."""

import re

import pytest

from ribcage.ballot.models import BallotRecord
from ribcage.readouts import tiebreaker
from ribcage.readouts.basis import Basis
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable import plan as the_ledger
from ribcage.timetable.models import Box, Timetable
from tests.http.test_pick_plan import text

COMPARE = "/console/pick/compare/"
SWAP = "/console/pick/swap/"


def film(title, runtime):
    return Suggestion.objects.create(title=title, suggester_name="x", approval=Approval.APPROVED, runtime=runtime)


@pytest.fixture
def room(voters, monkeypatch):
    """Cube and The Thing on the timetable: ada has 4, Dani 0 (he vetoed Cube), Hanna scored Cube 0 so has nothing representable and a sum of 0."""
    monkeypatch.setattr("ribcage.timetable.plan.batches.propose", lambda *given, **more: __import__("ribcage.timetable.batch", fromlist=["Batch"]).Batch((), 0, ""))
    Timetable.objects.create(pk=1, budget=540)
    cube, thing, alien = film("Cube", 90), film("The Thing", 109), film("Alien", 117)
    Box.objects.create(suggestion=cube, start=0)
    Box.objects.create(suggestion=thing, start=90)
    for voter, one, score, vetoed in [("ada", cube, 3, False), ("ada", thing, 1, False), ("Dani", thing, 2, False), ("Dani", cube, None, True), ("Hanna", cube, 0, False), ("Dani", alien, 3, False)]:
        BallotRecord.objects.create(voter=voters[voter], suggestion=one, score=score, vetoed=vetoed)
    return {"cube": cube, "thing": thing, "alien": alien, "voters": voters}


def strip(page):
    """The plan row's cells as (title, classes, shown figures)."""
    row = re.search(r'<tr class="slate-row" data-slate-row>(.*?)</tr>', page, re.S)[1]
    return [(title, classes, text(re.sub(r'<span class="visually-hidden">.*?</span>', "", inner))) for classes, title, inner in re.findall(r'<i class="slate-strip__cell([^"]*)" title="([^"]*)">(.*?)</i>', row, re.S)]


def test_under_leximin_the_strip_shows_each_counted_voters_sum_and_marks_every_voter_tied_for_the_lowest(admin, room, settings):
    settings.SLATE_TIEBREAKER = "leximin"

    cells = strip(admin.get(COMPARE).text)

    assert [title for title, _, _ in cells] == [
        "ada: Cube, 3, slate sum 4",
        "Dani, pins the floor: The Thing, 2, slate sum 0, the lowest",
        "Hanna: nothing representable, slate sum 0, the lowest",
    ]
    assert [classes.count("slate-strip__cell--lowest") for _, classes, _ in cells] == [0, 1, 1]
    assert [shown for _, _, shown in cells] == ["3 4", "2 ★ 0", "0"]


def test_a_voter_out_for_no_ballot_or_set_aside_shows_no_sum(admin, room, voters):
    BallotRecord.objects.filter(voter=voters["Hanna"]).delete()

    cells = strip(admin.get(COMPARE).text)

    assert cells[2][0] == "Hanna: no ballot" and "slate sum" not in cells[2][0] and cells[2][2] == ""
    assert [classes.count("lowest") for _, classes, _ in cells] == [0, 1, 0]
    row = the_ledger.load(basis=Basis(without=frozenset({voters["ada"].pk})))["sections"][0]["rows"][0]
    assert row["people"][0]["out"] == "set aside by knob" and row["people"][0]["sum"] is None and not row["people"][0]["lowest"]


def test_under_total_the_strip_shows_the_sums_with_no_mark(admin, room, settings):
    settings.SLATE_TIEBREAKER = "total"

    cells = strip(admin.get(COMPARE).text)

    assert [title for title, _, _ in cells][:2] == ["ada: Cube, 3, slate sum 4", "Dani, pins the floor: The Thing, 2, slate sum 0"]
    assert all("lowest" not in classes and "lowest" not in title for title, classes, _ in cells)


def column(page):
    header = re.search(r'<th scope="col" class="ledger__number" data-tiebreaker>(.*?)</th>', page)[1]
    return header, text(re.search(r'<td class="ledger__number slate-row__total">(.*?)</td>', page, re.S)[1])


def test_the_column_is_named_by_the_rule_and_reads_its_figure_and_distance(admin, room, settings):
    settings.SLATE_TIEBREAKER = "leximin"
    assert column(admin.get(COMPARE).text) == ("Leximin", "0 =")
    settings.SLATE_TIEBREAKER = "total"
    assert column(admin.get(COMPARE).text) == ("Total", "4 =")


def test_the_objective_line_adds_the_sorted_sums_under_leximin_only(admin, room, settings):
    line = lambda page: text(re.search(r'<p class="slate-row__objective[^>]*>(.*?)</p>', page, re.S)[1])
    settings.SLATE_TIEBREAKER = "leximin"
    assert line(admin.get(COMPARE).text).endswith("total 4 · leximin 0 · 0 · 4")
    settings.SLATE_TIEBREAKER = "total"
    assert line(admin.get(COMPARE).text).endswith("total 4")


def test_the_breakdowns_worst_served_is_the_strips_lowest_marked_voter_a_nothing_representable_voter_included(admin, room):
    BallotRecord.objects.filter(voter=room["voters"]["Dani"], suggestion=room["cube"]).update(vetoed=False, score=1)
    page = admin.get(COMPARE).text
    marked = [title.split(":")[0].split(",")[0] for title, classes, _ in strip(page) if "lowest" in classes]
    people = re.search(r'<table class="ledger slate-row__table slate-row__people-table">(.*?)</table>', page, re.S)[1]
    worst = [text(name) for name, served in re.findall(r'<td class="slate-row__person">(.*?)</td>.*?<td class="ledger__number slate-row__sum([^"]*)"', people, re.S) if "worst" in served]

    assert marked == ["Hanna"]
    assert [each.replace(" ★", "") for each in worst] == marked


def test_the_swap_shows_the_sorted_sums_before_and_after_beside_total_and_a_nothing_representable_voters_change(admin, room, settings):
    settings.SLATE_TIEBREAKER = "leximin"
    BallotRecord.objects.create(voter=room["voters"]["Hanna"], suggestion=room["alien"], score=-1)
    page = admin.get(SWAP, {"a": f"{room['cube'].pk},{room['thing'].pk}", "b": f"{room['thing'].pk},{room['alien'].pk}", "from": "The plan", "to": "Proposal 1"}).text
    rows = {text(name): text(value) for name, value in re.findall(r'<tr data-swap-\w+><th scope="row">(.*?)</th><td>(.*?)</td></tr>', page, re.S)}

    assert rows["Leximin"] == "0 · 0 · 4 → -1 · 1 · 5 −1 at 1st"
    assert rows["Total"] == "4 → 5"
    hanna = re.search(r'<tr data-swap-voter>\s*<td class="slate-row__person">Hanna</td>(.*?)</tr>', page, re.S)[1]
    assert "nothing representable" in hanna and "0 → -1" in text(hanna)


def test_the_swap_under_total_keeps_total_and_adds_no_row(admin, room, settings):
    settings.SLATE_TIEBREAKER = "total"

    page = admin.get(SWAP, {"a": str(room["cube"].pk), "b": str(room["alien"].pk), "from": "a", "to": "b"}).text

    assert "data-swap-tiebreaker" not in page and "data-swap-total" in page


def test_the_swap_data_gives_a_nothing_representable_voter_their_sum_change(room):
    BallotRecord.objects.create(voter=room["voters"]["Hanna"], suggestion=room["alien"], score=-1)

    found = the_ledger.swap_of([room["cube"].pk], [room["alien"].pk])

    assert {each["name"]: each["sum_change"] for each in found["moves"]} == {"ada": -3, "Dani": 3 + 2, "Hanna": -1}


@pytest.mark.parametrize("rule, plan_row, best_row", [("leximin", ("0", "−3 at 2nd"), ("0", "=")), ("total", ("6", "−2"), ("8", "="))])
def test_every_distance_is_measured_from_the_best_row_not_the_first(room, settings, rule, plan_row, best_row):
    settings.SLATE_TIEBREAKER = rule
    BallotRecord.objects.filter(voter=room["voters"]["ada"], suggestion=room["thing"]).update(score=3)
    better = the_ledger.Wanted("This batch", "Proposal 1", (room["thing"].pk, room["alien"].pk))

    sections = {each["name"]: each["rows"] for each in the_ledger.load([better])["sections"]}

    read = lambda row: (row["tiebreaker"]["value"], row["tiebreaker"]["distance"])
    assert read(sections["The plan"][0]) == plan_row
    assert read(sections["This batch"][0]) == best_row


def test_the_surfaces_count_the_voters_the_floor_set_counts(room, monkeypatch):
    """The strip's sums, the breakdown's worst served and the swap's sum change all follow `FloorSet.counted` (#177)."""
    from ribcage.readouts.floor import FloorSet

    monkeypatch.setattr(FloorSet, "counted", property(lambda self: tuple(voter for voter in self.members if voter == self.members[0])))
    BallotRecord.objects.create(voter=room["voters"]["Hanna"], suggestion=room["alien"], score=-1)

    ledger = the_ledger.load()
    row = ledger["sections"][0]["rows"][0]
    found = the_ledger.swap_of([room["cube"].pk], [room["alien"].pk])

    assert [each["sum"] for each in row["people"]].count(None) == len(row["people"]) - 1
    assert [each["sum_change"] for each in found["moves"]].count(None) == len(found["moves"]) - 1
