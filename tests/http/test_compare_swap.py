"""The swap on Compare: a tick on every row and the panel one GET answers under the current basis (#24, #170)."""

import re

import pytest
from django.conf import settings

from ribcage.ballot.models import BallotRecord
from ribcage.suggestions.models import Suggestion
from ribcage.timetable.models import Box, Timetable
from tests.http.test_compare_batch import COMPARE, film, text
from tests.http.test_compare_knobs import KNOB, set_aside
from tests.http.test_shortlist import KEEP

SWAP = "/console/pick/swap/"


@pytest.fixture
def room(voters):
    """Cube, The Thing and Alien in a 9 hour budget, Cube and The Thing on the timetable: ada loves Cube, Dani vetoed it and loves Alien."""
    Timetable.objects.create(pk=1, budget=540)
    cube, thing, alien = film("Cube", 90), film("The Thing", 109), film("Alien", 117)
    Box.objects.create(suggestion=cube, start=0)
    Box.objects.create(suggestion=thing, start=90)
    for voter, one, score, vetoed in [("ada", cube, 3, False), ("ada", thing, 1, False), ("Dani", thing, 2, False), ("Dani", cube, None, True), ("Dani", alien, 3, False)]:
        BallotRecord.objects.create(voter=voters[voter], suggestion=one, score=score, vetoed=vetoed)
    return {"cube": cube, "thing": thing, "alien": alien, "voters": voters}


def ids(*films):
    return ",".join(str(each.pk) for each in films)


def ask(admin, before, after, **more):
    return admin.get(SWAP, {"a": ids(*before), "b": ids(*after), "from": "The plan", "to": "Proposal 9", **more})


def lines(page, mark):
    return [text(each) for each in re.findall(rf"<(?:p|li)[^>]*{mark}[^>]*>(.*?)</(?:p|li)>", page, re.S)]


def numbers(page):
    return {name: text(value) for name, value in re.findall(r'<tr data-swap-\w+><th scope="row">(.*?)</th><td>(.*?)</td></tr>', page, re.S)}


def moves(page):
    return {text(name): text(rest) for name, rest in re.findall(r'<tr data-swap-voter>\s*<td class="slate-row__person">(.*?)</td>(.*?)</tr>', page, re.S)}


def test_every_row_carries_a_tick_holding_its_film_set(admin, room):
    page = admin.get(COMPARE).text
    rows = re.findall(r'<tr class="slate-row" data-slate-row>.*?</tr>', page, re.S)

    ticks = [re.search(r'<input type="checkbox" class="slate-row__tick" data-swap-tick value="([\d,]*)" data-label="([^"]*)"', each) for each in rows]

    assert all(ticks) and len(rows) >= 2
    assert ticks[0][2] == "The plan"
    assert set(ticks[0][1].split(",")) == {str(room["cube"].pk), str(room["thing"].pk)}
    assert 'id="swap-panel"' in page and "hidden" in re.search(r'<div class="swap-slot"[^>]*>', page)[0]


def test_a_kept_row_carries_the_tick_too(admin, room):
    admin.post(KEEP, {"films": ids(room["cube"], room["alien"])})

    page = admin.get(COMPARE).text
    kept = re.search(r'aria-label="Shortlist">(.*?)</tbody>', page, re.S)[1]

    assert f'data-swap-tick value="{room["cube"].pk},{room["alien"].pk}"' in kept or f'data-swap-tick value="{room["alien"].pk},{room["cube"].pk}"' in kept


def test_the_panel_answers_the_swap_from_the_plan_to_a_slate(admin, room):
    page = admin.get(SWAP, {"a": ids(room["cube"], room["thing"]), "b": ids(room["thing"], room["alien"]), "from": "The plan", "to": "Proposal 1"}).text

    assert "The plan → Proposal 1" in text(page)
    assert lines(page, "data-swap-shared") == ["Shared: The Thing"]
    assert lines(page, "data-swap-out") == ["Out: Cube"]
    assert lines(page, "data-swap-in") == ["In: Alien"]
    assert numbers(page) == {"Floor": "2 → 1", "Σrep": "5 → 4", "Total": "4 → 6", "Leximin": "0 · 4 → 1 · 5 +1 at 1st", "Screen time": "3h19m → 3h46m", "Vetoes in the room": "1 → 0 −1"}
    assert lines(page, "data-swap-film-out") == ["− Cube 90m · 1 pts · was ada's"]
    assert lines(page, "data-swap-film-in") == ["+ Alien 117m · 3 pts · now Dani's"]
    assert moves(page)["ada"].count("▼ 2") == 1 and "▲ 1" in moves(page)["Dani"]
    assert "4 → 1" in moves(page)["ada"] and "0 → 5" in moves(page)["Dani"]
    assert "no ballot" in moves(page)["Hanna"]
    assert "★" in moves(page)["Dani"] and "★" in moves(page)["ada"]


def test_the_panel_is_the_panel_alone_and_holds_no_trigger_content(admin, room):
    page = ask(admin, [room["cube"]], [room["alien"]]).text

    assert 'data-swap' in page and "slate-ledger" not in page and "<html" not in page
    assert "doesthedogdie" not in page.lower() and "data-dtdd" not in page


def test_the_swap_of_a_batch_row_and_the_plan_from_the_rows_ticks(admin, room):
    page = admin.get(COMPARE).text
    plan_tick = re.search(r'data-swap-tick value="([\d,]*)"', page)[1]
    batch_tick = re.search(r'aria-label="This batch">.*?data-swap-tick value="([\d,]*)"', page, re.S)[1]

    answer = admin.get(SWAP, {"a": plan_tick, "b": batch_tick})

    assert answer.status_code == 200 and "data-swap" in answer.text


def test_a_swap_with_itself_changes_nothing(admin, room):
    page = ask(admin, [room["cube"], room["thing"]], [room["thing"], room["cube"]]).text

    assert lines(page, "data-swap-out") == ["Out: none"] and lines(page, "data-swap-in") == ["In: none"]
    assert "identical film sets" in page
    assert numbers(page)["Total"] == "4 → 4" and "▲" not in page and "▼" not in page


def test_the_panel_reads_the_current_basis(admin, room):
    ada = room["voters"]["ada"]
    set_aside(admin, ada)

    page = ask(admin, [room["cube"], room["thing"]], [room["thing"], room["alien"]]).text

    assert "basis: without ada" in text(page)
    assert "set aside by knob" in moves(page)["ada"] and "▼" not in moves(page)["ada"]
    assert "– → –" in moves(page)["ada"]
    assert numbers(page)["Total"] == "0 → 5"


def test_the_panel_reads_disregarded_vetoes(admin, room):
    admin.post(KNOB, {"knob": "disregarded", "voter": room["voters"]["Dani"].pk, "on": "1"})

    page = ask(admin, [room["cube"], room["thing"]], [room["thing"], room["alien"]]).text

    assert "Dani's vetoes disregarded" in text(page)
    assert numbers(page)["Total"] == "6 → 6"


def test_a_plain_get_or_nonsense_redirects_to_compare(admin, room):
    for query in ({}, {"a": "1"}, {"a": "x", "b": "1"}, {"a": "1,,x", "b": ""}):
        assert admin.get(SWAP, query).headers["Location"] == COMPARE


def test_a_film_no_longer_in_the_pool_is_marked_on_its_side(admin, room):
    gone = room["alien"].pk
    BallotRecord.objects.filter(suggestion=gone).delete()
    Suggestion.objects.filter(pk=gone).delete()

    page = admin.get(SWAP, {"a": ids(room["cube"]), "b": f"{room['thing'].pk},{gone}"}).text

    assert lines(page, "data-swap-in") == ["In: The Thing"]
    assert lines(page, "data-swap-gone") == [f"No longer in the pool: film {gone} (after), not scored"]


def gone_films(*films):
    pks = [each.pk for each in films]
    BallotRecord.objects.filter(suggestion__in=pks).delete()
    Suggestion.objects.filter(pk__in=pks).delete()
    return pks


def test_a_film_no_longer_in_the_pool_is_marked_on_the_before_side(admin, room):
    [gone] = gone_films(room["alien"])

    page = admin.get(SWAP, {"a": f"{room['cube'].pk},{gone}", "b": ids(room["cube"])}).text

    assert lines(page, "data-swap-gone") == [f"No longer in the pool: film {gone} (before), not scored"]


def test_films_gone_on_both_sides_are_told_apart_by_a_separator(admin, room):
    before, after = gone_films(film("Gone before", 80), film("Gone after", 85))

    page = admin.get(SWAP, {"a": f"{room['cube'].pk},{before}", "b": f"{room['thing'].pk},{after}"}).text

    assert lines(page, "data-swap-gone") == [f"No longer in the pool: film {before} (before); film {after} (after), not scored"]


def test_a_swap_of_films_all_in_the_pool_marks_nothing_gone(admin, room):
    assert "data-swap-gone" not in ask(admin, [room["cube"]], [room["thing"]]).text


def test_an_empty_side_is_a_slate_of_no_films(admin, room):
    page = admin.get(SWAP, {"a": "", "b": ids(room["cube"])}).text

    assert lines(page, "data-swap-in") == ["In: Cube"]
    assert numbers(page)["Screen time"] == "0m → 1h30m"


def test_the_panel_slot_sits_in_place_at_full_size():
    css = (settings.BASE_DIR / "ribcage/static/theme/theme.css").read_text(encoding="utf-8")
    rule = re.search(r"^\.swap-slot \{(.*?)\}", css, re.S | re.M)[1]

    assert not any(word in rule for word in ("position", "max-height", "overflow"))


def test_the_panel_carries_a_clear_control(admin, room):
    page = ask(admin, [room["cube"]], [room["thing"]]).text

    assert 'data-swap-clear' in page and "Clear" in text(re.search(r"<button[^>]*data-swap-clear[^>]*>(.*?)</button>", page, re.S)[1])
