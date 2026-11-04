"""The plan as a slate ledger row on Compare, in every phase (#12, #15, #24, #147, #164)."""

import html
import re

import pytest
from django.conf import settings
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
    return re.search(r'<section class="compare".*?</section>', page, re.S)[0]


def cells(page, name):
    """The plan's main row by cell class, as text."""
    main = re.search(r'<tr class="slate-row" data-slate-row>(.*?)</tr>', the_plan(page), re.S)[1].replace("</span>", "").replace("<span", "<b")
    return {kind: text(re.search(rf'<td[^>]*class="[^"]*{name_}[^"]*"[^>]*>(.*?)</td>', main, re.S)[1]) for kind, name_ in name.items()}


def line(page):
    """Floor, Σrep and films as the old line read them, from the row."""
    row = cells(page, {"floor": "slate-row__floor", "sigma": "slate-row__sigma", "films": "slate-row__films"})
    return f"{row['films']} | floor {row['floor']} | Σrep {row['sigma']}"


def table(page):
    """Each voter's representative and score as the breakdown's People table gives them."""
    return {name: " ".join(rest) for name, *rest in breakdown(page, "people")}


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

    assert line(page) == "2 · 3h19m | floor 2 = | Σrep 5 ="
    assert table(page) == {
        "ada": "Cube 3 4",
        "Dani ★": "The Thing 2 0",
        "Hanna": "no ballot 0",
    }
    assert text(re.search(r'<p class="slate-row__vetoed">(.*?)</p>', page, re.S)[1]) == "Vetoed: Cube (Dani)"
    assert "Floor computed over 2 of 3 — Hanna: no ballot" in text(the_plan(page))


def test_the_line_says_over_past_the_budget_and_no_budget_without_one(admin, plan):
    Timetable.objects.update(budget=180)
    assert 'class="slate-row__over">over<' in admin.get(COMPARE).text
    assert line(admin.get(COMPARE).text) == "2 · 3h19m over | floor 2 = | Σrep 5 ="

    Timetable.objects.update(budget=None)
    assert line(admin.get(COMPARE).text) == "2 · 3h19m no budget | floor 2 = | Σrep 5 ="
    assert "slate-row__over" not in admin.get(COMPARE).text


def test_removing_a_box_changes_the_readouts_and_moving_one_does_not(admin, plan):
    before = the_plan(admin.get(COMPARE).text)
    Box.objects.filter(suggestion=plan["cube"]).update(start=300)
    assert the_plan(admin.get(COMPARE).text) == before

    Box.objects.filter(suggestion=plan["cube"]).delete()
    page = admin.get(COMPARE).text

    assert line(page) == "1 · 1h49m | floor 1 = | Σrep 3 ="
    assert table(page)["ada ★"].startswith("The Thing 1")
    assert "Vetoed: none" in text(the_plan(page))


def test_moving_a_box_keeps_a_tie_s_representative_and_the_vetoed_order(admin, plan):
    alien = put("Alien", 117, start=200)
    for voter, film, score, vetoed in [("Hanna", plan["cube"], 2, False), ("Hanna", plan["thing"], 2, False), ("Hanna", alien, None, True)]:
        BallotRecord.objects.create(voter=plan["voters"][voter], suggestion=film, score=score, vetoed=vetoed)

    def read():
        page = admin.get(COMPARE).text
        return table(page), text(re.search(r'<p class="slate-row__vetoed">(.*?)</p>', page, re.S)[1])

    before = read()
    Box.objects.filter(suggestion=plan["cube"]).update(start=500)

    assert before[0]["Hanna ★"].startswith("The Thing 2") and before[1] == "Vetoed: Cube (Dani); Alien (Hanna)"
    assert read() == before


def test_a_dropped_film_on_the_timetable_still_represents_and_an_empty_floor_set_has_no_floor(admin, plan):
    Suggestion.objects.filter(pk=plan["cube"].pk).update(approval=Approval.DROPPED)
    page = admin.get(COMPARE).text

    assert table(page)["ada"].startswith("Cube 3")

    BallotRecord.objects.all().delete()
    assert "floor no floor" in line(admin.get(COMPARE).text)


def test_a_timetable_with_no_boxes_says_so(admin, plan):
    Box.objects.all().delete()

    page = admin.get(COMPARE).text

    assert EMPTY in the_plan(page)
    assert "data-slate-row" not in page


def test_a_labelled_box_alone_is_a_plan_with_no_films(admin, voters):
    Box.objects.create(label="Dinner", length=45, start=0)

    assert line(admin.get(COMPARE).text) == "0 · 0m no budget | floor no floor | Σrep 0 ="


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


def breakdown(page, kind):
    return [
        [text(cell) for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        for row in re.findall(r"<tr>(.*?)</tr>", re.search(rf'<table class="ledger slate-row__table slate-row__{kind}-table">.*?</table>', page, re.S)[0], re.S)[1:]
    ]


def test_the_breakdown_lists_the_films_and_the_people_in_place(admin, plan):
    page = admin.get(COMPARE).text

    assert 'aria-expanded="false"' in the_plan(page) and "<dialog" not in the_plan(page) and "<details" not in the_plan(page)
    assert breakdown(page, "films") == [
        ["The Thing", "109m", "3", "Dani ★"],
        ["Cube", "90m", "1", "ada"],
    ]
    assert breakdown(page, "people") == [
        ["ada", "Cube", "3", "4"],
        ["Dani ★", "The Thing", "2", "0"],
        ["Hanna", "no ballot", "0"],
    ]
    assert re.search(r'slate-row__title slate-row__most">The Thing', page)


def test_a_film_representing_nobody_reads_how_many_like_it(admin, plan):
    ada = put("Alien", 117, start=199)
    BallotRecord.objects.create(voter=plan["voters"]["ada"], suggestion=ada, score=1)
    BallotRecord.objects.create(voter=plan["voters"]["Dani"], suggestion=ada, score=1)

    assert ["Alien", "117m", "2", "nobody · 2 like it"] in breakdown(admin.get(COMPARE).text, "films")


def test_a_voter_scoring_only_a_dropped_film_on_the_timetable_stays_out_of_the_floor_set(admin, plan):
    hanna = plan["voters"]["Hanna"]
    BallotRecord.objects.create(voter=hanna, suggestion=put("Ripley", 100, approval=Approval.DROPPED, start=200), score=3)

    assert "Hanna: no ballot" in text(admin.get(COMPARE).text)


def test_a_voter_at_zero_shows_their_best_eligible_film_never_a_dropped_one(admin, plan):
    voters = plan["voters"]
    ada = voters["ada"]
    BallotRecord.objects.filter(voter=ada).delete()
    BallotRecord.objects.create(voter=ada, suggestion=plan["cube"], vetoed=True)
    BallotRecord.objects.create(voter=ada, suggestion=plan["thing"], seen_it=True, score=3)
    BallotRecord.objects.create(voter=ada, suggestion=put("Tron", 96, suggester=ada), score=2)
    BallotRecord.objects.create(voter=ada, suggestion=put("Ripley", 100, approval=Approval.DROPPED, suggester=ada), score=3)

    people = dict((each[0], each) for each in breakdown(admin.get(COMPARE).text, "people"))

    assert people["ada ★"] == ["ada ★", "0 · best eligible: Tron (96m, scored 2)", "1"]


def test_the_best_and_worst_served_slate_sums_are_coloured(admin, plan):
    page = admin.get(COMPARE).text

    assert re.search(r"slate-row__sum--best\">4<", page)
    assert re.search(r"slate-row__sum--worst\">0<", page)


def test_the_breakdown_query_count_does_not_grow_with_the_slate(admin, plan):
    def queries():
        with CaptureQueriesContext(connection) as captured:
            admin.get(COMPARE)
        return len(captured)

    admin.get(COMPARE)
    small = queries()
    for number in range(6):
        film = put(f"More {number}", 80, start=300 + 100 * number)
        BallotRecord.objects.create(voter=plan["voters"]["ada"], suggestion=film, score=2)
        BallotRecord.objects.create(voter=plan["voters"]["Dani"], suggestion=film, vetoed=True)
        put(f"Unplaced {number}", 80)

    assert queries() == small


def test_the_coloured_sums_outrank_the_ledger_cell_ink():
    css = (settings.BASE_DIR / "ribcage/static/theme/theme.css").read_text(encoding="utf-8")

    assert "[data-skin] .ledger td.slate-row__sum--best {" in css
    assert "[data-skin] .ledger td.slate-row__sum--worst {" in css


def test_the_plan_is_a_slate_ledger_row_with_its_tier_standing_strip_vetoes_and_dots(admin, plan):
    page = the_plan(admin.get(COMPARE).text)

    assert re.findall(r'<tbody class="slate-ledger__section" aria-label="([^"]*)"', page) == ["The plan"]
    assert cells(page, {"label": "slate-row__label", "vetoes": "slate-row__vetoes"}) == {"label": "The plan best on screen", "vetoes": "1"}
    assert re.findall(r'<i class="slate-strip__cell ([^"]*)" title="([^"]*)"', page)[:2] == [
        ("score--top-pick", "ada: Cube, 3"),
        ("score--keen", "Dani, pins the floor: The Thing, 2"),
    ]
    assert 'slate-strip__cell slate-strip__cell--out" title="Hanna: no ballot"' in page
    assert text(re.search(r'<span class="slate-row__tier">(.*?)</span>', page, re.S)[1]) == "tier 1"
    assert 'class="slate-strip__pin">★' in page
    assert re.findall(r'<th scope="col" class="slate-ledger__film[^"]*"><span title="([^"]*)"', page) == ["The Thing", "Cube"]
    assert page.count('class="slate-dot__mark"') == 2
    assert text(re.search(r'<p class="slate-row__objective[^>]*>(.*?)</p>', page, re.S)[1]) == "floor 2 · Σrep 5 · total 4"
    assert "DoesTheDogDie" not in page


def test_removing_the_floor_pinners_film_changes_the_floor_and_the_strip(admin, plan):
    assert cells(admin.get(COMPARE).text, {"floor": "slate-row__floor"}) == {"floor": "2 ="}
    Box.objects.filter(suggestion=plan["thing"]).delete()
    page = admin.get(COMPARE).text

    assert cells(page, {"floor": "slate-row__floor"}) == {"floor": "0 ="}
    assert re.findall(r'<i class="slate-strip__cell ([^"]*)" title="([^"]*)"', page)[1] == ("score--dont-mind", "Dani, pins the floor: nothing on the slate")


def test_the_ledger_loads_further_rows_in_the_same_queries(admin, plan):
    from ribcage.timetable import plan as the_ledger

    def queries(wanted):
        with CaptureQueriesContext(connection) as captured:
            the_ledger.load(wanted)
        return len(captured)

    films = [put(f"Extra {number}", 80).pk for number in range(8)]
    for pk in films:
        BallotRecord.objects.create(voter=plan["voters"]["ada"], suggestion_id=pk, score=2)
    one = [the_ledger.Wanted("This batch", "Proposal 1", tuple(films[:3]))]
    many = [the_ledger.Wanted("Shortlist" if number % 2 else "This batch", f"Row {number}", tuple(films[number : number + 3])) for number in range(5)]

    assert queries(one) == queries(many) == queries(())
    ledger = the_ledger.load(many)
    assert [each["name"] for each in ledger["sections"]] == ["The plan", "Shortlist", "This batch"]
    assert [len(each["rows"]) for each in ledger["sections"]] == [1, 2, 3]


def test_an_empty_timetable_leaves_the_other_rows_core_alone(admin, plan):
    from ribcage.timetable import plan as the_ledger

    Box.objects.all().delete()
    ledger = the_ledger.load([the_ledger.Wanted("This batch", "One", (plan["cube"].pk,))])

    assert ledger["empty"] and [each["core"] for each in ledger["columns"]] == [False]
