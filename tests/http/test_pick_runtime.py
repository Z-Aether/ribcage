"""Correcting a film's runtime from its box on the track, through the ripple mode (#22, #142)."""

import re

import pytest

from ribcage.console.films import HELD
from ribcage.suggestions import runtime
from ribcage.suggestions.models import Approval, RuntimeSource, Suggestion
from ribcage.timetable.models import Box
from tests.films import a_tmdb_film

PICK, ANCHOR = "/console/pick/", "/console/pick/anchor/"
PREVIEW, SAVE = "/console/pick/preview/", "/console/pick/runtime/"
FILMS_RUNTIME = "/console/films/runtime/"


@pytest.fixture
def evening(admin, voters):
    """Cube 0–90, Dinner 100–145, The Thing 160–269, from 18:00."""
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})
    cube = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(431, "Cube", runtime=90), "Six strangers.")
    thing = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing", runtime=109), "Lights off.")
    Suggestion.objects.filter(pk__in=[cube.pk, thing.pk]).update(approval=Approval.APPROVED)
    return {
        "admin": admin,
        "cube_film": cube,
        "cube": Box.objects.create(suggestion=cube, start=0),
        "dinner": Box.objects.create(label="Dinner", length=45, start=100),
        "thing": Box.objects.create(suggestion=thing, start=160),
    }


def starts():
    return dict(Box.objects.values_list("pk", "start"))


def stored(film):
    return Suggestion.objects.get(pk=film.pk)


def test_a_save_writes_the_runtime_and_the_pushed_boxes_together(evening):
    response = evening["admin"].post(SAVE, {"box": evening["cube"].pk, "runtime": "120", "mode": "keep-gaps"})

    assert response.headers["Location"] == f"{PICK}?box={evening['cube'].pk}"
    assert stored(evening["cube_film"]).runtime == 120
    # 0–120 touches Dinner at 100, so Dinner and The Thing move by the 30.
    assert starts() == {evening["cube"].pk: 0, evening["dinner"].pk: 130, evening["thing"].pk: 190}


def test_under_none_a_longer_runtime_only_overlaps(evening):
    evening["admin"].post(SAVE, {"box": evening["cube"].pk, "runtime": "120", "mode": "none"})

    assert stored(evening["cube_film"]).runtime == 120
    assert starts() == {evening["cube"].pk: 0, evening["dinner"].pk: 100, evening["thing"].pk: 160}


def test_a_save_without_a_mode_uses_the_sessions(evening):
    evening["admin"].post("/console/pick/mode/", {"mode": "keep-gaps"})
    evening["admin"].post(SAVE, {"box": evening["cube"].pk, "runtime": "120"})

    assert starts()[evening["dinner"].pk] == 130


def test_the_preview_shows_the_same_boxes_and_writes_nothing(evening):
    asked = {"box": evening["cube"].pk, "runtime": "120", "mode": "keep-gaps", "selected": evening["cube"].pk}
    page = evening["admin"].post(PREVIEW, asked).text

    assert stored(evening["cube_film"]).runtime == 90
    assert starts()[evening["dinner"].pk] == 100
    assert re.search(rf'id="box-{evening["dinner"].pk}"[^>]*data-start="130"', page)
    assert 'id="track-region"' in page and "<html" not in page


@pytest.mark.parametrize("typed", ["", "  ", "abc", "0", "-5", "1.5", "99999"])
def test_a_refused_runtime_saves_neither_the_runtime_nor_a_push_and_keeps_what_was_typed(evening, typed):
    response = evening["admin"].post(SAVE, {"box": evening["cube"].pk, "runtime": typed, "mode": "keep-gaps"})

    assert response.status_code == 200
    assert stored(evening["cube_film"]).runtime == 90
    assert starts() == {evening["cube"].pk: 0, evening["dinner"].pk: 100, evening["thing"].pk: 160}
    assert f'value="{typed}"' in response.text
    assert 'id="box-runtime-refusal"' in response.text


def test_an_empty_runtime_is_refused_with_held_and_the_others_with_the_runtime_parsers_words(evening):
    assert HELD in evening["admin"].post(SAVE, {"box": evening["cube"].pk, "runtime": ""}).text
    assert runtime.NOT_WHOLE_MINUTES in evening["admin"].post(SAVE, {"box": evening["cube"].pk, "runtime": "abc"}).text


def test_a_preview_of_a_refused_runtime_shows_the_stored_track(evening):
    page = evening["admin"].post(PREVIEW, {"box": evening["cube"].pk, "runtime": "", "mode": "keep-gaps", "selected": evening["cube"].pk})

    assert page.status_code == 200
    assert re.search(rf'id="box-{evening["dinner"].pk}"[^>]*data-start="100"', page.text)


def test_reset_offers_tmdbs_value_while_it_differs_and_saving_it_reads_tmdb_again(evening):
    assert "TMDB says" not in evening["admin"].get(f"{PICK}?box={evening['cube'].pk}").text
    evening["admin"].post(SAVE, {"box": evening["cube"].pk, "runtime": "120", "mode": "none"})
    film = stored(evening["cube_film"])
    assert film.runtime_source is not RuntimeSource.TMDB and film.film.runtime_source.value == "hand-entered"

    page = evening["admin"].get(f"{PICK}?box={evening['cube'].pk}").text
    assert re.search(r'TMDB says 90 · <button[^>]*data-reset="90"', page)

    evening["admin"].post(SAVE, {"box": evening["cube"].pk, "runtime": "90", "mode": "none"})
    assert stored(evening["cube_film"]).film.runtime_source.value == "tmdb"
    assert "TMDB says" not in evening["admin"].get(f"{PICK}?box={evening['cube'].pk}").text


def test_the_panel_carries_the_runtime_box_with_its_words_and_names_where_it_lands(evening):
    page = evening["admin"].get(f"{PICK}?box={evening['cube'].pk}").text

    assert "The film&#x27;s runtime everywhere — SOLVE reads it too." in page or "The film's runtime everywhere — SOLVE reads it too." in page
    assert 'action="/console/pick/runtime/"' in page and re.search(r'<form[^>]*pick/runtime/[^>]*data-lands-on="/console/pick/"', page)


def test_a_films_tab_edit_lengthens_the_box_and_moves_no_other_box(evening):
    before = starts()

    evening["admin"].post(FILMS_RUNTIME, {"suggestion": evening["cube_film"].pk, "runtime": "130", "show": "all"})

    assert stored(evening["cube_film"]).runtime == 130
    assert starts() == before


def test_a_box_gone_or_a_labelled_one_changes_nothing_and_reloads(evening):
    gone = evening["admin"].post(SAVE, {"box": "99999", "runtime": "120"})
    labelled = evening["admin"].post(SAVE, {"box": evening["dinner"].pk, "runtime": "120"})

    assert gone.status_code == labelled.status_code
    assert Box.objects.get(pk=evening["dinner"].pk).length == 45
    assert evening["admin"].get(SAVE).status_code == 302
