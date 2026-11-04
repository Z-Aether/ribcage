"""*Use this slate* from Compare: a batch row or a kept row arms the Timetable tab, Cancel returns to Compare (#12, #36, #172)."""

import re
from datetime import UTC, datetime

import pytest

from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box
from tests.http.test_compare_batch import COMPARE
from tests.http.test_compare_swap import ids, room  # noqa: F401
from tests.http.test_shortlist import KEEP

PICK, USE, PREVIEW = "/console/pick/", "/console/pick/use/", "/console/pick/preview/"


@pytest.fixture
def anchored(room):  # noqa: F811
    from ribcage.timetable.models import Timetable

    Timetable.objects.update(anchor=datetime(2026, 11, 7, 17, 0, tzinfo=UTC))
    return room


def batch_rows(page):
    return re.findall(r'<tr class="slate-row" data-slate-row>.*?</tr>', page, re.S)


def stored():
    return [(each.suggestion.title, each.start) for each in Box.objects.select_related("suggestion").order_by("start")]


def uses(page):
    return re.findall(r'<input type="hidden" name="use" value="([^"]*)"><input type="hidden" name="back" value="compare">', page)


def test_every_batch_row_and_kept_row_offers_use_and_the_plans_row_none(admin, anchored):
    admin.post(KEEP, {"films": ids(anchored["cube"], anchored["alien"])})

    page = admin.get(COMPARE).text
    rows = batch_rows(page)

    assert "data-use" not in rows[0] and "The plan" in rows[0]
    assert all("data-use" in each for each in rows[1:]) and len(rows) >= 3
    assert any(re.fullmatch(r"\d+", value) for value in uses(page))
    assert any(value.startswith("films:") for value in uses(page))


def test_use_sets_the_compare_scroll_aside_for_cancel_rather_than_keeping_it_for_the_armed_tab(admin, anchored):
    page = admin.get(COMPARE).text

    forms = re.findall(r'<form method="get"[^>]*>(?:(?!</form>).)*name="back"', page, re.S)
    assert forms and all("data-sets-aside" in each.split(">")[0] for each in forms)


def test_use_on_a_batch_row_arms_the_timetable_with_its_films_in_slate_order_writing_nothing(admin, anchored):
    before = stored()
    value = next(each for each in uses(admin.get(COMPARE).text) if each.startswith("films:"))
    films = {int(each) for each in value[len("films:") :].split(",")}

    page = admin.get(PICK, {"use": value, "back": "compare"}).text

    assert stored() == before
    assert "data-armed" in page and "Use this proposal" in page
    starts = [int(each) for each in re.findall(r'class="track__slot[^"]*"[^>]*data-start="(-?\d+)"', page)]
    assert len(starts) == len(films) and starts == sorted(starts) and starts[0] == 0
    assert re.search(r'<a class="button button--quiet arrange__cancel" href="/console/pick/compare/" data-restores-aside>Cancel</a>', page)


def test_apply_lays_a_batch_proposals_films_in_slate_order(admin, anchored):
    value = f"films:{ids(anchored['cube'], anchored['thing'], anchored['alien'])}"

    admin.post(USE, {"use": value})

    assert stored() == [("Alien", 0), ("The Thing", 117), ("Cube", 226)]


def test_cancel_goes_to_the_timetable_when_not_armed_from_compare(admin, anchored):
    value = f"films:{ids(anchored['cube'])}"

    page = admin.get(PICK, {"use": value}).text

    assert re.search(r'arrange__cancel" href="/console/pick/">Cancel</a>', page)


def test_the_preview_route_keeps_the_way_back(admin, anchored):
    page = admin.post(PREVIEW, {"use": f"films:{ids(anchored['cube'])}", "back": "compare"}).text

    assert 'href="/console/pick/compare/" data-restores-aside>Cancel' in page


def test_a_batch_proposal_holding_a_film_dropped_since_writes_nothing(admin, anchored):
    value = f"films:{ids(anchored['cube'], anchored['alien'])}"
    Suggestion.objects.filter(pk=anchored["alien"].pk).update(approval=Approval.DROPPED)
    before = stored()

    armed = admin.get(PICK, {"use": value, "back": "compare"}).text
    admin.post(USE, {"use": value})

    assert "data-armed" not in armed
    assert stored() == before


def test_a_nonsense_batch_key_writes_nothing(admin, anchored):
    before = stored()

    for value in ("films:", "films:x", "films:99999"):
        admin.post(USE, {"use": value})
        assert "data-armed" not in admin.get(PICK, {"use": value}).text

    assert stored() == before


def test_use_on_a_kept_row_arms_its_kept_proposal(admin, anchored):
    admin.post(KEEP, {"films": ids(anchored["cube"], anchored["alien"])})
    kept = next(each for each in uses(admin.get(COMPARE).text) if re.fullmatch(r"\d+", each))

    page = admin.get(PICK, {"use": kept, "back": "compare"}).text

    assert "Use Kept 1: 2 films" in page and 'href="/console/pick/compare/" data-restores-aside>Cancel' in page


def test_without_an_anchor_use_is_disabled_on_compare_with_the_line(admin, room):  # noqa: F811
    admin.post(KEEP, {"films": ids(room["cube"], room["alien"])})

    page = admin.get(COMPARE).text
    rows = batch_rows(page)[1:]

    assert rows and all(re.search(r"<button[^>]*data-use disabled", each) and "Set the start time above first." in each for each in rows)
