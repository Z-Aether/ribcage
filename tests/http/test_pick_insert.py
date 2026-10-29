"""Dragging a candidate onto the track: a preview that writes nothing, a save that adds the box, and a film gone since (#22, #144)."""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box
from tests.films import a_tmdb_film

PICK, ANCHOR = "/console/pick/", "/console/pick/anchor/"
PREVIEW, PLACE = "/console/pick/preview/", "/console/pick/place/"


@pytest.fixture
def evening(admin, voters):
    """Cube 0–90, Dinner 100–145, The Thing 160–269 from 18:00, and Alien (117 minutes) approved and not placed."""
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})
    films = {}
    for tmdb, title, runtime in ((431, "Cube", 90), (1091, "The Thing", 109), (348, "Alien", 117)):
        films[title] = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(tmdb, title, runtime=runtime), "Why.")
    Suggestion.objects.filter(pk__in=[each.pk for each in films.values()]).update(approval=Approval.APPROVED)
    return {
        "admin": admin,
        "alien": films["Alien"],
        "cube": Box.objects.create(suggestion=films["Cube"], start=0),
        "dinner": Box.objects.create(label="Dinner", length=45, start=100),
        "thing": Box.objects.create(suggestion=films["The Thing"], start=160),
    }


def starts():
    return dict(Box.objects.values_list("pk", "start"))


def slot_start(page, key):
    found = re.search(rf'<div id="box-{key}" class="track__slot[^"]*"[^>]*data-start="(-?\d+)" data-length="(\d+)"', page)
    return (int(found.group(1)), int(found.group(2))) if found else None


def test_an_insert_preview_writes_nothing_and_shows_the_box_the_save_would_add(evening):
    before = starts()

    response = evening["admin"].post(PREVIEW, {"suggestion": evening["alien"].pk, "start": "300"})

    assert starts() == before and Box.objects.count() == 3
    page = response.text
    assert 'id="track-region"' in page and "<html" not in page
    assert slot_start(page, "new") == (300, 117)
    assert slot_start(page, evening["thing"].pk) == (160, 109)


def test_an_insert_preview_goes_through_the_ripple_mode_and_still_writes_nothing(evening):
    before = starts()

    none = evening["admin"].post(PREVIEW, {"suggestion": evening["alien"].pk, "start": "150", "mode": "none"}).text
    pushed = evening["admin"].post(PREVIEW, {"suggestion": evening["alien"].pk, "start": "150", "mode": "keep-gaps"}).text

    assert slot_start(none, evening["thing"].pk) == (160, 109) and "overlap" in none
    # Alien 150–267 lands on The Thing (160): it moves to 267, 107 on.
    assert slot_start(pushed, evening["thing"].pk) == (267, 109)
    assert starts() == before


def test_a_save_adds_the_box_the_preview_showed_and_selects_it(evening):
    asked = {"suggestion": evening["alien"].pk, "start": "150", "mode": "keep-gaps"}
    previewed = evening["admin"].post(PREVIEW, asked).text

    response = evening["admin"].post(PLACE, asked)

    box = Box.objects.get(suggestion=evening["alien"])
    assert box.start == 150
    assert response.headers["Location"] == f"{PICK}?box={box.pk}"
    page = evening["admin"].get(response.headers["Location"]).text
    for key, new in ((evening["thing"].pk, evening["thing"].pk), ("new", box.pk), (evening["dinner"].pk, evening["dinner"].pk)):
        assert slot_start(page, new) == slot_start(previewed, key)
    # The film has left the list.
    assert "No approved film is left to place." in page
    # The pushed box is stored where the preview said.
    assert starts()[evening["thing"].pk] == 267


def test_an_insert_of_a_placed_or_dropped_or_gone_film_changes_nothing_and_reloads_the_tab(evening):
    placed = Suggestion.objects.get(box=evening["cube"])
    dropped = evening["alien"]
    Suggestion.objects.filter(pk=dropped.pk).update(approval=Approval.DROPPED)
    before = starts()

    for film in (placed.pk, dropped.pk, 99999, "x"):
        for route in (PREVIEW, PLACE):
            asked = {"suggestion": film, "start": "300", "mode": "keep-gaps"}
            assert evening["admin"].post(route, asked, HTTP_HX_REQUEST="true").headers["HX-Redirect"] == PICK
            assert evening["admin"].post(route, asked).headers["Location"] == PICK

    assert starts() == before and Box.objects.count() == 3


def test_an_insert_with_no_anchor_changes_nothing(admin, voters):
    film = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(348, "Alien", runtime=117), "Why.")
    Suggestion.objects.filter(pk=film.pk).update(approval=Approval.APPROVED)

    assert admin.post(PLACE, {"suggestion": film.pk, "start": "0"}).headers["Location"] == PICK
    assert Box.objects.count() == 0


@pytest.mark.parametrize("asked", [{"start": "5"}, {"suggestion": "1"}, {"suggestion": "1", "start": "ten"}, {"suggestion": "1", "start": "9999999"}, {"suggestion": "1", "start": "5", "mode": "gaps"}])
def test_a_post_that_is_no_inserts_is_refused_and_writes_nothing(evening, asked):
    before = starts()

    assert evening["admin"].post(PLACE, asked).status_code == 400
    if "suggestion" in asked:
        assert evening["admin"].post(PREVIEW, asked).status_code == 400
    assert starts() == before


def test_the_preview_can_hold_the_scale_still(evening):
    page = evening["admin"].post(PREVIEW, {"suggestion": evening["alien"].pk, "start": "300", "scale_start": "-200", "scale_length": "1000"}).text

    assert 'data-scale-start="-200" data-scale-length="1000"' in page


def test_the_insert_preview_costs_a_flat_number_of_queries(evening):
    with CaptureQueriesContext(connection) as few:
        evening["admin"].post(PREVIEW, {"suggestion": evening["alien"].pk, "start": "300"})
    for number in range(5):
        Box.objects.create(label=f"Break {number}", length=15, start=400 + number * 20)
    with CaptureQueriesContext(connection) as more:
        evening["admin"].post(PREVIEW, {"suggestion": evening["alien"].pk, "start": "300"})

    assert len(more) == len(few)


def test_the_candidates_are_draggable_only_over_a_track(admin, voters, evening):
    page = admin.get(PICK).text
    assert f'data-drag-film="{evening["alien"].pk}" data-length="117"' in page
    assert 'class="track-place"' in page and 'data-lands-on="/console/pick/"' in page

    Box.objects.all().delete()
    assert "data-drag-film" not in admin.get(PICK).text


def test_with_no_anchor_nothing_is_draggable(admin, voters):
    film = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(348, "Alien", runtime=117), "Why.")
    Suggestion.objects.filter(pk=film.pk).update(approval=Approval.APPROVED)

    page = admin.get(PICK).text

    assert "Alien" in page and "data-drag-film" not in page


def test_a_save_lays_the_box_through_laying_and_writes_nothing_where_laying_refuses(evening, monkeypatch):
    from ribcage.timetable import editing, laying

    before = starts()
    asked = (evening["alien"].pk, 150, "keep-gaps")
    monkeypatch.setattr(laying, "lay_film", lambda *args, **kwargs: None)

    assert editing.insert(*asked, save=True) is None
    assert starts() == before and Box.objects.count() == 3


def test_laying_a_film_at_a_start_puts_it_there(evening):
    from ribcage.timetable import laying

    assert laying.lay_film(evening["alien"].pk, 300).start == 300
    assert laying.lay_film(evening["alien"].pk, 310) is None
