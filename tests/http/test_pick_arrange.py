"""The arrange utilities by arming: a GET that shows the result, Apply that stores it, Cancel that changes nothing (#22, #145)."""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box
from tests.films import a_tmdb_film

PICK, ANCHOR = "/console/pick/", "/console/pick/anchor/"
PREVIEW, APPLY = "/console/pick/preview/", "/console/pick/arrange/"
LAY = f"{PICK}?arrange=lay-out&minutes=10"
SPREAD = f"{PICK}?arrange=spread"


@pytest.fixture
def evening(admin, voters):
    """Cube 100–190, Dinner 200–245 (flexible) and The Thing 400–509 from 18:00."""
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})
    films = {}
    for tmdb, title, runtime in ((431, "Cube", 90), (1091, "The Thing", 109)):
        films[title] = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(tmdb, title, runtime=runtime), "Why.")
    Suggestion.objects.filter(pk__in=[each.pk for each in films.values()]).update(approval=Approval.APPROVED)
    return {
        "admin": admin,
        "cube": Box.objects.create(suggestion=films["Cube"], start=100),
        "dinner": Box.objects.create(label="Dinner", length=45, start=200, flexible=True),
        "thing": Box.objects.create(suggestion=films["The Thing"], start=400),
    }


def starts():
    return dict(Box.objects.values_list("pk", "start"))


def shown(page, key):
    found = re.search(rf'<div id="box-{key}" class="track__slot[^"]*"[^>]*data-start="(-?\d+)" data-length="(\d+)"', page)
    return (int(found.group(1)), int(found.group(2))) if found else None


def test_arming_writes_nothing_and_shows_the_arranged_track_with_apply_and_cancel(evening):
    before = starts()

    page = evening["admin"].get(LAY).text

    assert starts() == before
    assert shown(page, evening["cube"].pk) == (0, 90)
    assert shown(page, evening["dinner"].pk) == (100, 45)
    assert shown(page, evening["thing"].pk) == (155, 109)
    assert 'action="/console/pick/arrange/"' in page and ">Apply</button>" in page and ">Cancel</a>" in page
    assert "Lay out with a break of 10 min" in page
    assert re.search(r"<form[^>]*pick/arrange/[^>]*data-lands-on=\"/console/pick/\"", page)


def test_apply_stores_what_arming_showed_and_the_tab_reloads_unarmed(evening):
    armed = evening["admin"].get(LAY).text

    response = evening["admin"].post(APPLY, {"arrange": "lay-out", "minutes": "10"})

    assert response.headers["Location"] == PICK
    page = evening["admin"].get(PICK).text
    for box in ("cube", "dinner", "thing"):
        assert shown(page, evening[box].pk) == shown(armed, evening[box].pk)
    assert starts() == {evening["cube"].pk: 0, evening["dinner"].pk: 100, evening["thing"].pk: 155}
    # Lengths stay full, the flexible box's included.
    assert Box.objects.get(pk=evening["dinner"].pk).length == 45
    assert ">Apply</button>" not in page


def test_spread_applies_on_the_grid_from_the_anchor_to_the_last_end(evening):
    # Last end 509; 244 of film and dinner; 265 spare over 2 gaps = 132.5.
    armed = evening["admin"].get(SPREAD).text
    assert shown(armed, evening["thing"].pk)[0] % 5 == 0

    evening["admin"].post(APPLY, {"arrange": "spread"})

    assert starts() == {evening["cube"].pk: 0, evening["dinner"].pk: 225, evening["thing"].pk: 400}
    assert shown(armed, evening["dinner"].pk)[0] == 225


def test_apply_arranges_the_timetable_as_it_is_then_not_as_it_was_armed(evening):
    evening["admin"].get(LAY)
    Box.objects.filter(pk=evening["thing"].pk).update(start=-50)

    evening["admin"].post(APPLY, {"arrange": "lay-out", "minutes": "0"})

    assert starts() == {evening["thing"].pk: 0, evening["cube"].pk: 109, evening["dinner"].pk: 199}


def test_cancel_shows_the_timetable_as_it_is(evening):
    before = starts()
    evening["admin"].get(LAY)

    page = evening["admin"].get(PICK).text

    assert starts() == before
    assert shown(page, evening["cube"].pk) == (100, 90)
    assert ">Apply</button>" not in page
    assert re.search(r'<a class="button button--quiet arrange__cancel" href="/console/pick/">Cancel', evening["admin"].get(LAY).text)


def test_the_ripple_mode_plays_no_part(evening):
    for mode in ("none", "keep-gaps", "keep-end-time"):
        evening["admin"].post("/console/pick/mode/", {"mode": mode})
        page = evening["admin"].get(LAY).text
        assert shown(page, evening["thing"].pk) == (155, 109)


def test_the_preview_route_answers_an_armed_utility_with_the_track_alone(evening):
    before = starts()

    page = evening["admin"].post(PREVIEW, {"arrange": "lay-out", "minutes": "10"}).text

    assert 'id="track-region"' in page and "<html" not in page
    assert shown(page, evening["thing"].pk) == (155, 109) and ">Apply</button>" in page
    assert starts() == before


def test_neither_is_offered_without_an_anchor(admin):
    page = admin.get(PICK).text
    assert re.search(r'name="arrange" value="lay-out"[^>]*disabled', page)
    assert re.search(r'name="arrange" value="spread"[^>]*disabled', page)

    Box.objects.create(label="Break", length=30, start=0)
    assert ">Apply</button>" not in admin.get(LAY).text
    assert admin.post(APPLY, {"arrange": "lay-out", "minutes": "10"}).headers["Location"] == PICK
    assert admin.post(PREVIEW, {"arrange": "spread"}, HTTP_HX_REQUEST="true").headers["HX-Redirect"] == PICK
    assert Box.objects.get().start == 0


def test_they_are_offered_when_there_is_an_anchor_and_a_box(evening):
    page = evening["admin"].get(PICK).text

    assert not re.search(r'name="arrange" value="lay-out"[^>]*disabled', page)
    assert re.search(r'name="minutes" value="15"', page)


@pytest.mark.parametrize("asked", [{}, {"arrange": "shuffle"}, {"arrange": "lay-out", "minutes": "-5"}, {"arrange": "lay-out", "minutes": "ten"}, {"arrange": "lay-out", "minutes": "99999"}])
def test_a_post_that_names_no_utility_is_refused_and_writes_nothing(evening, asked):
    before = starts()

    assert evening["admin"].post(APPLY, asked).status_code == 400
    assert starts() == before


def test_a_get_that_names_no_utility_arms_nothing(evening):
    for query in ("arrange=shuffle", "arrange=lay-out&minutes=-1", "arrange=lay-out&minutes=x"):
        assert ">Apply</button>" not in evening["admin"].get(f"{PICK}?{query}").text


def test_the_arranged_preview_costs_a_flat_number_of_queries(evening):
    with CaptureQueriesContext(connection) as few:
        evening["admin"].post(PREVIEW, {"arrange": "spread"})
    for number in range(5):
        Box.objects.create(label=f"Break {number}", length=15, start=600 + number * 20)
    with CaptureQueriesContext(connection) as more:
        evening["admin"].post(PREVIEW, {"arrange": "spread"})

    assert len(more) == len(few)


def an_unplaced_film(voters):
    alien = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(348, "Alien", runtime=117), "Why.")
    Suggestion.objects.filter(pk=alien.pk).update(approval=Approval.APPROVED)
    return alien


def test_a_move_and_an_insert_preview_keep_the_utilities_on(evening, voters):
    alien = an_unplaced_film(voters)
    moved = evening["admin"].post(PREVIEW, {"box": evening["thing"].pk, "start": "450", "mode": "none"}).text
    inserted = evening["admin"].post(PREVIEW, {"suggestion": alien.pk, "start": "700"}).text
    for page in (moved, inserted):
        assert 'name="arrange" value="lay-out"' in page
        assert not re.search(r'name="arrange" value="(lay-out|spread)"[^>]*disabled', page)
        assert re.search(r'name="minutes" value="15"', page)
        assert not re.search(r'class="button--quiet" disabled[^>]*>\+ Break', page) and "Set the start time first" not in page


def test_an_armed_track_is_inert(evening, voters):
    an_unplaced_film(voters)
    page = evening["admin"].get(f"{LAY}&box={evening['cube'].pk}").text

    assert "data-armed" in page
    assert "track__handle" not in page.split('class="track"', 1)[1]
    assert 'class="box-panel' not in page
    assert "data-drag-film" not in page
    assert re.search(r'candidate__add.*?<button[^>]*disabled', page, re.S)
    assert "data-armed" not in evening["admin"].get(PICK).text
