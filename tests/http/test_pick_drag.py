"""Dragging a box: a preview that writes nothing, a save that stores what the preview showed, and a box gone since (#22, #139)."""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box
from tests.films import a_tmdb_film

PICK, ANCHOR = "/console/pick/", "/console/pick/anchor/"
PREVIEW, MOVE = "/console/pick/preview/", "/console/pick/move/"


@pytest.fixture
def evening(admin, voters):
    """Cube 0–90, Dinner 100–145, The Thing 160–269, from 18:00."""
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})
    cube = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(431, "Cube", runtime=90), "Six strangers.")
    thing = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing", runtime=109), "Lights off.")
    Suggestion.objects.filter(pk__in=[cube.pk, thing.pk]).update(approval=Approval.APPROVED)
    return {
        "admin": admin,
        "cube": Box.objects.create(suggestion=cube, start=0),
        "dinner": Box.objects.create(label="Dinner", length=45, start=100),
        "thing": Box.objects.create(suggestion=thing, start=160),
    }


def starts():
    return dict(Box.objects.values_list("pk", "start"))


def slot_of(page, box):
    return re.search(rf'<div id="box-{box.pk}" class="track__slot[^"]*" style="([^"]*)"[^>]*data-start="(-?\d+)"', page)


def test_a_preview_writes_nothing_and_answers_with_the_track_showing_the_move_and_its_overlaps(evening):
    before = starts()

    response = evening["admin"].post(PREVIEW, {"box": evening["thing"].pk, "start": "120"})

    assert starts() == before
    page = response.text
    assert slot_of(page, evening["thing"]).group(2) == "120"
    assert 'id="track-region"' in page and "<html" not in page
    # Dinner 100–145 and The Thing 120–229 now share 25 minutes.
    assert "1 overlap" in page and page.count('class="track__overlap"') == 1
    assert page.count("box--overlapping") == 2
    # Only the moved box changed.
    assert slot_of(page, evening["dinner"]).group(2) == "100" and slot_of(page, evening["cube"]).group(2) == "0"


def test_a_save_stores_exactly_what_the_preview_showed(evening):
    asked = {"box": evening["thing"].pk, "start": "-35"}
    previewed = evening["admin"].post(PREVIEW, asked).text

    response = evening["admin"].post(MOVE, asked)

    assert starts() == {evening["cube"].pk: 0, evening["dinner"].pk: 100, evening["thing"].pk: -35}
    assert response.headers["Location"] == f"{PICK}?box={evening['thing'].pk}"
    # The tab as stored shows the same starts, overlaps and tool row the preview did.
    page = evening["admin"].get(PICK).text
    for box in evening.values():
        if isinstance(box, Box):
            assert slot_of(page, box).group(2) == slot_of(previewed, box).group(2)
    assert re.search(r"(\d+) overlaps?", page).group() == re.search(r"(\d+) overlaps?", previewed).group()


def test_a_preview_can_hold_the_scale_still(evening):
    page = evening["admin"].post(PREVIEW, {"box": evening["thing"].pk, "start": "160", "scale_start": "-200", "scale_length": "1000"}).text

    assert 'data-scale-start="-200" data-scale-length="1000"' in page
    assert "--at: 20.000%" in slot_of(page, evening["cube"]).group(1)


def test_a_preview_and_a_save_naming_a_removed_box_reload_the_tab(evening):
    gone = evening["dinner"].pk
    evening["dinner"].delete()
    before = starts()

    for route in (PREVIEW, MOVE):
        response = evening["admin"].post(route, {"box": gone, "start": "50"}, HTTP_HX_REQUEST="true")
        assert response.headers["HX-Redirect"] == PICK
        assert evening["admin"].post(route, {"box": gone, "start": "50"}).headers["Location"] == PICK

    assert starts() == before


@pytest.mark.parametrize("asked", [{"start": "5"}, {"box": "x", "start": "5"}, {"box": "1"}, {"box": "1", "start": "ten"}, {"box": "1", "start": "9999999"}, {"box": "1", "start": "5", "mode": "gaps"}])
def test_a_post_that_is_no_drags_is_refused_and_writes_nothing(evening, asked):
    before = starts()

    assert [evening["admin"].post(route, asked).status_code for route in (PREVIEW, MOVE)] == [400, 400]
    assert starts() == before


def test_the_preview_costs_a_flat_number_of_queries(evening):
    with CaptureQueriesContext(connection) as few:
        evening["admin"].post(PREVIEW, {"box": evening["thing"].pk, "start": "120"})
    for start in (200, 300, 400):
        Box.objects.create(label="Break", length=30, start=start)
    with CaptureQueriesContext(connection) as many:
        evening["admin"].post(PREVIEW, {"box": evening["thing"].pk, "start": "120"})

    assert len(many) == len(few)


def test_the_move_form_names_where_it_lands_and_the_slots_carry_their_minutes(evening):
    page = evening["admin"].get(PICK).text

    assert re.search(r'<form[^>]*pick/move/[^>]*data-preview="/console/pick/preview/"[^>]*data-lands-on="/console/pick/"', page)
    assert slot_of(page, evening["dinner"]).group(2) == "100" and 'data-length="45"' in page
    assert re.search(r"<script src=\"[^\"]*timetable/drag[^\"]*.js\"", page)


def test_a_preview_marks_the_pages_own_selection_not_the_box_being_dragged(evening):
    page = evening["admin"].post(PREVIEW, {"box": evening["cube"].pk, "start": "30", "selected": evening["dinner"].pk}).text

    assert "is-selected" in slot_of_class(page, evening["dinner"])
    assert "is-selected" not in slot_of_class(page, evening["cube"])


def test_a_preview_naming_no_selection_marks_none(evening):
    page = evening["admin"].post(PREVIEW, {"box": evening["cube"].pk, "start": "30"}).text

    assert "is-selected" not in page


def slot_of_class(page, box):
    return re.search(rf'<div id="box-{box.pk}" class="([^"]*)"', page).group(1)
