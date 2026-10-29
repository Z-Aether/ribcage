"""The ripple mode: sticky in the admin's session, and Push · keep gaps through a drag, a typed length and a save (#13, #22, #140)."""

import re

import pytest
from django.test import Client

from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box
from tests.films import a_tmdb_film
from tests.http.signing_in import sign_in_as_the_admin

PICK, ANCHOR, MODE = "/console/pick/", "/console/pick/anchor/", "/console/pick/mode/"
PREVIEW, MOVE, SAVE_BOX, REMOVE = "/console/pick/preview/", "/console/pick/move/", "/console/pick/box/", "/console/pick/remove/"
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
        "dinner": Box.objects.create(label="Dinner", length=45, start=100),
        "thing": Box.objects.create(suggestion=thing, start=160),
    }


def starts():
    return dict(Box.objects.values_list("pk", "start"))



def shown_mode(page):
    return re.search(r'<input type="hidden" name="mode" value="([^"]+)">', page).group(1)


def test_the_mode_defaults_to_none_and_the_tool_row_offers_the_choices(evening):
    page = evening["admin"].get(PICK).text

    assert "On a clash:" in page and "None" in page and "Push · keep gaps" in page
    assert shown_mode(page) == NONE
    assert 'value="none" class="button--quiet ripple-mode__choice is-chosen"' in page


def test_the_mode_persists_across_requests_in_the_admin_session(evening):
    evening["admin"].post(MODE, {"mode": GAPS})

    for _ in range(2):
        page = evening["admin"].get(PICK).text
        assert shown_mode(page) == GAPS
        assert 'value="keep-gaps" class="button--quiet ripple-mode__choice is-chosen"' in page


def test_setting_the_mode_reloads_the_tab_with_its_selection_and_nonsense_changes_nothing(evening):
    response = evening["admin"].post(MODE, {"mode": GAPS, "selected": evening["dinner"].pk})
    assert response.headers["Location"] == f"{PICK}?box={evening['dinner'].pk}"

    evening["admin"].post(MODE, {"mode": "squeeze"})
    assert shown_mode(evening["admin"].get(PICK).text) == GAPS
    assert evening["admin"].get(MODE).headers["Location"] == PICK


def test_the_mode_is_the_admins_alone_and_a_new_admin_session_starts_on_none(evening):
    evening["admin"].post(MODE, {"mode": GAPS})
    stranger = Client()

    assert "login" in stranger.post(MODE, {"mode": GAPS}).headers["Location"]
    # Signing in again makes a fresh session, which holds no mode.
    sign_in_as_the_admin(stranger)
    assert shown_mode(stranger.get(PICK).text) == NONE


def test_the_panel_names_the_mode_the_page_shows(evening):
    evening["admin"].post(MODE, {"mode": GAPS})

    page = evening["admin"].get(f"{PICK}?box={evening['dinner'].pk}").text

    assert re.search(r'<form[^>]*pick/box/[^>]*data-preview="/console/pick/preview/".*?name="mode" value="keep-gaps"', page, re.S)


def test_a_save_under_keep_gaps_stores_the_pushed_boxes(evening):
    # Cube 0–90 moved to 30 ends at 120, into Dinner at 100; everything after moves 30.
    evening["admin"].post(MOVE, {"box": evening["cube"].pk, "start": "30", "mode": GAPS})

    assert starts() == {evening["cube"].pk: 30, evening["dinner"].pk: 130, evening["thing"].pk: 190}


def test_a_preview_under_keep_gaps_shows_what_the_save_stores_and_writes_nothing(evening):
    asked = {"box": evening["cube"].pk, "start": "30", "mode": GAPS}
    before = starts()

    page = evening["admin"].post(PREVIEW, asked).text

    assert starts() == before
    assert 'data-start="130"' in page and 'data-start="190"' in page
    evening["admin"].post(MOVE, asked)
    assert starts() == {evening["cube"].pk: 30, evening["dinner"].pk: 130, evening["thing"].pk: 190}


def test_the_same_move_under_none_pushes_nothing(evening):
    evening["admin"].post(MOVE, {"box": evening["cube"].pk, "start": "30", "mode": NONE})

    assert starts() == {evening["cube"].pk: 30, evening["dinner"].pk: 100, evening["thing"].pk: 160}


def test_a_typed_length_previews_without_writing_and_saves_the_same_result(evening):
    typed = {"box": evening["dinner"].pk, "length": "75", "mode": GAPS}
    before = starts()

    previewed = evening["admin"].post(PREVIEW, typed).text

    assert starts() == before and Box.objects.get(pk=evening["dinner"].pk).length == 45
    assert 'id="track-region"' in previewed and "<html" not in previewed
    assert re.search(rf'id="box-{evening["thing"].pk}"[^>]*data-start="190"', previewed)
    assert re.search(rf'id="box-{evening["dinner"].pk}"[^>]*data-start="100" data-length="75"', previewed)

    evening["admin"].post(SAVE_BOX, {"box": evening["dinner"].pk, "label": "Dinner", "length": "75", "mode": GAPS})
    assert Box.objects.get(pk=evening["dinner"].pk).length == 75
    assert starts() == {evening["cube"].pk: 0, evening["dinner"].pk: 100, evening["thing"].pk: 190}


def test_a_typed_length_short_of_contact_pushes_nothing(evening):
    evening["admin"].post(SAVE_BOX, {"box": evening["dinner"].pk, "label": "Dinner", "length": "60", "mode": GAPS})

    assert starts() == {evening["cube"].pk: 0, evening["dinner"].pk: 100, evening["thing"].pk: 160}


def test_the_panel_save_without_a_mode_uses_the_sessions(evening):
    evening["admin"].post(MODE, {"mode": GAPS})

    evening["admin"].post(SAVE_BOX, {"box": evening["dinner"].pk, "label": "Dinner", "length": "75"})

    assert starts()[evening["thing"].pk] == 190


@pytest.mark.parametrize("length", ["", "7", "9", "x", "12.5", "9999999"])
def test_a_typed_length_that_would_be_refused_answers_the_stored_track(evening, length):
    answer = evening["admin"].post(PREVIEW, {"box": evening["dinner"].pk, "length": length, "mode": GAPS})

    assert answer.status_code == 200 and 'id="track-region"' in answer.text
    assert re.search(rf'id="box-{evening["thing"].pk}"[^>]*data-start="160"', answer.text)
    assert re.search(rf'id="box-{evening["dinner"].pk}"[^>]*data-start="100" data-length="45"', answer.text)


def test_the_previewed_answer_carries_the_selected_boxs_end_for_the_panel(evening):
    answer = evening["admin"].post(PREVIEW, {"box": evening["dinner"].pk, "selected": evening["dinner"].pk, "length": "90", "mode": GAPS}).text
    stored = evening["admin"].get(PICK, {"box": evening["dinner"].pk}).text

    previewed_span = re.search(r'data-selected-span="([^"]+)"', answer).group(1)
    stored_span = re.search(r"<strong data-box-span>([^<]+)</strong>", stored).group(1)
    assert previewed_span != stored_span


def test_the_move_route_does_not_write_a_typed_length(evening):
    answer = evening["admin"].post(MOVE, {"box": evening["dinner"].pk, "length": "90", "mode": GAPS})

    assert answer.status_code == 400
    assert Box.objects.get(pk=evening["dinner"].pk).length == 45 and starts()[evening["thing"].pk] == 160


def test_a_save_refused_over_the_label_still_shows_the_typed_length_on_the_track(evening):
    page = evening["admin"].post(SAVE_BOX, {"box": evening["dinner"].pk, "label": " ", "length": "90", "mode": GAPS}).text

    assert "The label is empty" in page and 'value="90"' in page
    assert re.search(rf'id="box-{evening["dinner"].pk}"[^>]*data-start="100" data-length="90"', page)
    assert re.search(rf'id="box-{evening["thing"].pk}"[^>]*data-start="205"', page)
    assert Box.objects.get(pk=evening["dinner"].pk).length == 45 and starts()[evening["thing"].pk] == 160


def test_a_film_boxs_length_is_no_typed_edit(evening):
    assert evening["admin"].post(PREVIEW, {"box": evening["cube"].pk, "length": "30", "mode": GAPS}).status_code == 400
    assert Box.objects.get(pk=evening["cube"].pk).length is None


def test_remove_moves_nothing_under_a_push_mode(evening):
    evening["admin"].post(MODE, {"mode": GAPS})

    evening["admin"].post(REMOVE, {"box": evening["dinner"].pk})

    assert starts() == {evening["cube"].pk: 0, evening["thing"].pk: 160}


def test_the_move_form_names_the_sessions_mode_and_the_script_for_typed_lengths_loads(evening):
    evening["admin"].post(MODE, {"mode": GAPS})

    page = evening["admin"].get(f"{PICK}?box={evening['dinner'].pk}").text

    assert re.search(r'pick/move/.*?name="mode" value="keep-gaps"', page, re.S)
    assert re.search(r'<script src="[^"]*timetable/typed[^"]*\.js"', page)
