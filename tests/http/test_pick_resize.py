"""Resizing a labelled box by its handle: a length preview that writes nothing, a save through the labelled box's one write, a gone box (#22, #143)."""

import re

import pytest

from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box
from tests.films import a_tmdb_film

PICK, ANCHOR, MODE = "/console/pick/", "/console/pick/anchor/", "/console/pick/mode/"
PREVIEW, MOVE, RESIZE = "/console/pick/preview/", "/console/pick/move/", "/console/pick/resize/"
GAPS, NONE = "keep-gaps", "none"


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
        "dinner": Box.objects.create(label="Dinner", length=45, start=100, flexible=True),
        "thing": Box.objects.create(suggestion=thing, start=160),
    }


def starts():
    return dict(Box.objects.values_list("pk", "start"))


def test_a_length_preview_writes_nothing_and_flags_the_overlap_under_none(evening):
    before = starts()

    page = evening["admin"].post(PREVIEW, {"box": evening["dinner"].pk, "length": "75", "mode": NONE}).text

    assert starts() == before and Box.objects.get(pk=evening["dinner"].pk).length == 45
    assert re.search(rf'id="box-{evening["dinner"].pk}"[^>]*data-start="100" data-length="75"', page)
    assert "1 overlap" in page


def test_a_save_under_none_stores_the_length_and_pushes_nothing(evening):
    before = starts()

    response = evening["admin"].post(RESIZE, {"box": evening["dinner"].pk, "length": "75", "mode": NONE})

    assert response.headers["Location"] == f"{PICK}?box={evening['dinner'].pk}"
    assert Box.objects.get(pk=evening["dinner"].pk).length == 75 and starts() == before


def test_a_save_under_keep_gaps_stores_the_length_and_pushes_the_tail_by_the_change_in_end(evening):
    previewed = evening["admin"].post(PREVIEW, {"box": evening["dinner"].pk, "length": "75", "mode": GAPS}).text

    evening["admin"].post(RESIZE, {"box": evening["dinner"].pk, "length": "75", "mode": GAPS})

    assert Box.objects.get(pk=evening["dinner"].pk).length == 75
    assert starts()[evening["thing"].pk] == 190 and starts()[evening["cube"].pk] == 0
    assert re.search(rf'id="box-{evening["thing"].pk}"[^>]*data-start="190"', previewed)


def test_a_save_keeps_the_label_and_the_flexible_flag(evening):
    evening["admin"].post(RESIZE, {"box": evening["dinner"].pk, "length": "60", "mode": NONE})

    box = Box.objects.get(pk=evening["dinner"].pk)
    assert (box.label, box.flexible, box.length) == ("Dinner", True, 60)


@pytest.mark.parametrize("length", ["0", "4", "-5", "", "x", "7", "9999999"])
def test_a_length_the_box_cannot_hold_is_refused_and_nothing_is_stored(evening, length):
    before = starts()

    response = evening["admin"].post(RESIZE, {"box": evening["dinner"].pk, "length": length, "mode": GAPS})

    assert response.status_code == 400
    assert Box.objects.get(pk=evening["dinner"].pk).length == 45 and starts() == before


def test_the_smallest_length_is_five_minutes(evening):
    evening["admin"].post(RESIZE, {"box": evening["dinner"].pk, "length": "5", "mode": NONE})

    assert Box.objects.get(pk=evening["dinner"].pk).length == 5


def test_a_film_box_is_never_resized(evening):
    response = evening["admin"].post(RESIZE, {"box": evening["cube"].pk, "length": "30", "mode": GAPS})

    assert Box.objects.get(pk=evening["cube"].pk).length is None
    assert response.status_code in (302, 400) and starts()[evening["thing"].pk] == 160


def test_a_box_gone_since_reloads_the_tab_as_it_is_now(evening):
    gone = evening["dinner"].pk
    Box.objects.filter(pk=gone).delete()

    save = evening["admin"].post(RESIZE, {"box": gone, "length": "75", "mode": NONE})
    htmx = evening["admin"].post(RESIZE, {"box": gone, "length": "75", "mode": NONE}, HTTP_HX_REQUEST="true")
    preview = evening["admin"].post(PREVIEW, {"box": gone, "length": "75", "mode": NONE}, HTTP_HX_REQUEST="true")

    assert save.headers["Location"] == PICK
    assert htmx.headers["HX-Redirect"] == PICK and preview.headers["HX-Redirect"] == PICK


def test_a_box_gone_since_reloads_the_tab_on_a_preview_the_save_would_refuse(evening):
    gone = evening["dinner"].pk
    Box.objects.filter(pk=gone).delete()

    preview = evening["admin"].post(PREVIEW, {"box": gone, "length": "9", "mode": NONE}, HTTP_HX_REQUEST="true")

    assert preview.headers["HX-Redirect"] == PICK


def test_the_move_route_still_refuses_a_length(evening):
    evening["admin"].post(MOVE, {"box": evening["dinner"].pk, "length": "90", "mode": GAPS})

    assert Box.objects.get(pk=evening["dinner"].pk).length == 45


def test_only_a_labelled_box_carries_a_handle_and_the_resize_form_names_the_mode(evening):
    evening["admin"].post(MODE, {"mode": GAPS})

    page = evening["admin"].get(PICK).text

    slots = re.split(r'<div id="box-', page)[1:]
    with_handle = {int(slot.split('"')[0]) for slot in slots if "track__handle" in slot}
    assert with_handle == {evening["dinner"].pk}
    assert re.search(r'pick/resize/.*?name="mode" value="keep-gaps"', page, re.S)
    assert re.search(r'<script src="[^"]*timetable/drag[^"]*\.js"', page)
