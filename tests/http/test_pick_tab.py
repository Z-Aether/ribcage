"""PICK's header and its two sub-tabs, the anchor and the budget, and a box's hold on its film (#24, #36, #135)."""

import html
import re
from datetime import datetime, timezone as utc

import pytest

from ribcage.phase.order import PHASES, Phase
from ribcage.suggestions.models import Suggestion
from ribcage.timetable import setting
from ribcage.timetable.models import Box, Timetable
from tests.films import a_tmdb_film
from tests.http.test_phase import walk_to
from tests.http.test_runtime_box import EDIT, HELD, stored
from tests.http.test_runtime_pencil import pencils_on

PICK, COMPARE, ANCHOR, BUDGET = "/console/pick/", "/console/pick/compare/", "/console/pick/anchor/", "/console/pick/budget/"
NEEDS_AN_ANCHOR = "Set the start time above first."
EMPTY = "Nothing on the timetable yet."
CURRENT = ' aria-current="page"'


def value(page, name):
    return html.unescape(re.search(rf'<input [^>]*name="{name}" value="([^"]*)"', page)[1])


def sub_tabs(page):
    nav = re.search(r'<nav class="pick-subtabs".*?</nav>', page, re.S)[0]
    return re.findall(r'<a href="([^"]+)"( aria-current="page")?>(\w+)</a>', nav)


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("path", [PICK, COMPARE])
def test_each_sub_tab_renders_in_every_phase(admin, phase, path):
    walk_to(phase)

    response = admin.get(path)

    assert response.status_code == 200
    assert 'name="anchor"' in response.text and 'name="hours"' in response.text


def test_the_pick_tab_opens_on_timetable_and_each_sub_tab_has_its_own_address(admin):
    assert sub_tabs(admin.get(PICK).text) == [(PICK, CURRENT, "Timetable"), (COMPARE, "", "Compare")]
    assert sub_tabs(admin.get(COMPARE).text) == [(PICK, "", "Timetable"), (COMPARE, CURRENT, "Compare")]
    assert 'href="/console/pick/" aria-current="page">Pick' in admin.get(COMPARE).text



def test_an_empty_anchor_says_to_set_it_first_and_a_set_one_says_the_timetable_is_empty(admin):
    assert NEEDS_AN_ANCHOR in admin.get(PICK).text
    assert EMPTY not in admin.get(PICK).text

    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})

    assert EMPTY in admin.get(PICK).text
    assert NEEDS_AN_ANCHOR not in admin.get(PICK).text


def test_the_anchor_saves_as_an_instant_and_renders_in_the_deployments_time_zone(admin, settings):
    settings.TIME_ZONE = "Europe/Budapest"

    response = admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})

    assert (response.status_code, response.headers["Location"]) == (302, PICK)
    assert Timetable.objects.get().anchor == datetime(2026, 11, 7, 17, 0, tzinfo=utc.utc)
    page = admin.get(PICK).text
    assert value(page, "anchor") == "2026-11-07T18:00"
    assert "Saturday 7 November, 18:00" in page


def test_the_anchor_can_be_changed_and_a_save_from_compare_returns_to_compare(admin):
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})

    response = admin.post(ANCHOR, {"anchor": "2026-11-08T19:30", "sub": "compare"})

    assert response.headers["Location"] == COMPARE
    assert value(admin.get(PICK).text, "anchor") == "2026-11-08T19:30"


@pytest.mark.parametrize("typed", ["", "   ", "tomorrow", "2026-13-45T10:00"])
def test_an_empty_or_unreadable_anchor_is_refused_keeping_what_was_typed(admin, typed):
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})

    response = admin.post(ANCHOR, {"anchor": typed})

    assert response.status_code == 200
    assert setting.NO_ANCHOR in html.unescape(response.text)
    assert value(response.text, "anchor") == typed
    assert Timetable.objects.get().anchor == datetime(2026, 11, 7, 18, 0, tzinfo=utc.utc)


@pytest.mark.parametrize("typed", ["0001-01-01T00:30"])
def test_an_anchor_at_the_calendars_edge_is_refused_not_a_500(admin, settings, typed):
    settings.TIME_ZONE = "Europe/Budapest"
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})

    response = admin.post(ANCHOR, {"anchor": typed})

    assert response.status_code == 200
    assert setting.NO_ANCHOR in html.unescape(response.text)
    assert value(response.text, "anchor") == typed


def test_the_budget_saves_as_whole_minutes_and_reads_back_as_hours_and_minutes(admin):
    admin.post(BUDGET, {"hours": "9", "minutes": "30"})

    assert Timetable.objects.get().budget == 570
    page = admin.get(PICK).text
    assert (value(page, "hours"), value(page, "minutes")) == ("9", "30")
    assert "9 h 30 min of screen time" in page


def test_a_blank_budget_clears_it_to_no_budget(admin):
    admin.post(BUDGET, {"hours": "9", "minutes": ""})

    response = admin.post(BUDGET, {"hours": "", "minutes": " "})

    assert response.status_code == 302
    assert Timetable.objects.get().budget is None
    assert "No budget." in admin.get(PICK).text


@pytest.mark.parametrize("typed", [("x", "30"), ("-1", "0"), ("1", "75"), ("0", "0"), ("1000", "")])
def test_an_unreadable_budget_is_refused_keeping_what_was_typed(admin, typed):
    admin.post(BUDGET, {"hours": "9", "minutes": ""})

    response = admin.post(BUDGET, {"hours": typed[0], "minutes": typed[1]})

    assert response.status_code == 200
    assert setting.NO_BUDGET in html.unescape(response.text)
    assert (value(response.text, "hours"), value(response.text, "minutes")) == typed
    assert Timetable.objects.get().budget == 540


@pytest.mark.parametrize("path", [ANCHOR, BUDGET, "/console/pick/box/"])
def test_a_get_to_a_save_lands_on_the_tab(admin, path):
    assert admin.get(path).headers["Location"] == PICK


def test_a_set_anchor_and_budget_survive_a_phase_move(admin):
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})
    admin.post(BUDGET, {"hours": "9", "minutes": ""})
    walk_to(Phase.RUN)

    page = admin.get(PICK).text

    assert (value(page, "anchor"), value(page, "hours")) == ("2026-11-07T18:00", "9")


# A box holds its film


@pytest.fixture
def boxed(voters):
    walk_to(Phase.SUGGEST)
    suggestion = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing", runtime=109), "Lights off.")
    Box.objects.create(suggestion=suggestion, start=0)
    return suggestion


def test_a_boxed_film_is_not_withdrawable_and_its_withdraw_changes_nothing(client, voters, boxed):
    client.force_login(voters["Hanna"])

    client.post("/withdraw/", {"suggestion": boxed.pk}, headers={"HX-Request": "true"})

    assert Suggestion.objects.filter(pk=boxed.pk).exists()
    assert Box.objects.count() == 1


def test_a_boxed_films_runtime_pencil_is_not_offered(client, voters, boxed):
    client.force_login(voters["Hanna"])

    assert pencils_on(client.get("/").text) == []


def test_the_films_tab_refuses_to_clear_a_boxed_films_runtime(admin, boxed):
    response = admin.post(EDIT, {"suggestion": boxed.pk, "runtime": ""})

    assert stored(boxed)[0] == 109
    assert HELD in html.unescape(response.text)


def test_a_boxed_film_still_takes_a_new_runtime(admin, boxed):
    admin.post(EDIT, {"suggestion": boxed.pk, "runtime": "120"})

    assert stored(boxed)[0] == 120
