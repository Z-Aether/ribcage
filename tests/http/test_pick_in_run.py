"""Actualising: every edit of the Pick tab works in RUN as in PICK, and the evening's poll answers the edited evening (#13, #162)."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from django.test import Client

from ribcage.phase.history import move
from ribcage.phase.order import Phase
from ribcage.timetable import engine
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box, Timetable
from tests.films import a_tmdb_film
from tests.http.test_phase import walk_to

PICK, ANCHOR, BUDGET = "/console/pick/", "/console/pick/anchor/", "/console/pick/budget/"
PREVIEW, MOVE, RESIZE, MODE = "/console/pick/preview/", "/console/pick/move/", "/console/pick/resize/", "/console/pick/mode/"
BOX, RUNTIME, ADD, PLACE = "/console/pick/box/", "/console/pick/runtime/", "/console/pick/add/", "/console/pick/place/"
BREAK, REMOVE, ARRANGE = "/console/pick/break/", "/console/pick/remove/", "/console/pick/arrange/"
FILMS_RUNTIME = "/console/films/runtime/"
GAPS, END_TIME, NONE = "keep-gaps", "keep-end-time", "none"


@pytest.fixture
def running(admin, voters):
    """RUN with Cube 0–90, Dinner 100–145, The Thing 160–269 from the anchor, and Alien approved but off the timetable."""
    walk_to(Phase.PICK)
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})
    films = {}
    for tmdb_id, title, runtime in ((431, "Cube", 90), (1091, "The Thing", 109), (348, "Alien", 117)):
        films[title] = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(tmdb_id, title, runtime=runtime), "Pitch.")
    Suggestion.objects.update(approval=Approval.APPROVED)
    boxes = {
        "cube": Box.objects.create(suggestion=films["Cube"], start=0),
        "dinner": Box.objects.create(label="Dinner", length=45, start=100),
        "thing": Box.objects.create(suggestion=films["The Thing"], start=160),
    }
    move(Phase.PICK, Phase.RUN)
    voter = Client()
    voter.force_login(voters["ada"])
    return {"admin": admin, "voter": voter, "films": films, **boxes}


def evening(running):
    """The (start, end) of each slot the poll answers, as minutes from the anchor."""
    answer = running["voter"].get("/evening/", headers={"HX-Request": "true"})
    assert answer.status_code == 200 and answer.text.lstrip().startswith('<section class="evening"')
    anchor = Timetable.objects.get().anchor
    found = re.findall(r'data-start="([^"]+)" data-end="([^"]+)"', answer.text)
    def minutes(text):
        return int((datetime.fromisoformat(text) - anchor.astimezone(UTC)) / timedelta(minutes=1))

    return sorted((minutes(start), minutes(end)) for start, end in found)


def test_the_fixture_is_in_run_with_the_evening_as_laid(running):
    assert evening(running) == [(0, 90), (100, 145), (160, 269)]


def test_a_drag_previews_then_saves_under_keep_gaps_and_the_evening_follows(running):
    asked = {"box": running["dinner"].pk, "start": "120", "mode": GAPS}
    before = evening(running)

    preview = running["admin"].post(PREVIEW, asked)
    assert preview.status_code == 200 and evening(running) == before
    running["admin"].post(MOVE, asked)

    assert evening(running) == [(0, 90), (120, 165), (180, 289)]


def test_a_move_under_none_pushes_nothing_and_a_push_may_carry_a_box_before_the_anchor(running):
    running["admin"].post(MOVE, {"box": running["cube"].pk, "start": "-30", "mode": NONE})
    assert evening(running) == [(-30, 60), (100, 145), (160, 269)]

    running["admin"].post(MOVE, {"box": running["dinner"].pk, "start": "-20", "mode": GAPS})
    assert (-20, 25) in evening(running)


def slack_after_the_thing(running):
    """Alien laid at 320–437, so a 51-minute gap follows The Thing: keep end time can take a push out of it and hold the last end."""
    Box.objects.create(suggestion=running["films"]["Alien"], start=320)


# Dinner dragged 20 later into The Thing: keep gaps carries every later box, keep end time spreads the push over the gaps so Alien's end holds at 437.
DRAGGED = {
    NONE: [(0, 90), (120, 165), (160, 269), (320, 437)],
    GAPS: [(0, 90), (120, 165), (180, 289), (340, 457)],
    END_TIME: [(0, 90), (120, 165), (175, 284), (320, 437)],
}
# Dinner lengthened 45 -> 75, the same way.
LENGTHENED = {
    NONE: [(0, 90), (100, 175), (160, 269), (320, 437)],
    GAPS: [(0, 90), (100, 175), (190, 299), (350, 467)],
    END_TIME: [(0, 90), (100, 175), (185, 294), (320, 437)],
}
# Cube 90 -> 120 reaches Dinner, so the later boxes are Dinner, The Thing and Alien.
RUNTIME_CHANGED = {
    NONE: [(100, 145), (160, 269), (320, 437)],
    GAPS: [(130, 175), (190, 299), (350, 467)],
    END_TIME: [(125, 170), (180, 289), (320, 437)],
}


@pytest.mark.parametrize("mode", engine.MODES)
def test_a_drag_under_each_ripple_mode_previews_then_saves_and_the_evening_follows(running, mode):
    slack_after_the_thing(running)
    asked = {"box": running["dinner"].pk, "start": "120", "mode": mode}
    before = evening(running)

    assert running["admin"].post(PREVIEW, asked).status_code == 200 and evening(running) == before
    running["admin"].post(MOVE, asked)

    assert evening(running) == DRAGGED[mode]


@pytest.mark.parametrize("mode", engine.MODES)
def test_a_handle_resize_under_each_ripple_mode_previews_then_saves_and_the_evening_follows(running, mode):
    slack_after_the_thing(running)
    asked = {"box": running["dinner"].pk, "length": "75", "mode": mode}
    before = evening(running)

    assert running["admin"].post(PREVIEW, asked).status_code == 200 and evening(running) == before
    running["admin"].post(RESIZE, asked)

    assert evening(running) == LENGTHENED[mode]
    assert Box.objects.get(pk=running["dinner"].pk).length == 75


@pytest.mark.parametrize("mode", engine.MODES)
def test_a_typed_length_from_the_box_panel_ripples_under_each_ripple_mode(running, mode):
    slack_after_the_thing(running)
    running["admin"].post(BOX, {"box": running["dinner"].pk, "label": "Dinner", "length": "75", "mode": mode})

    assert evening(running) == LENGTHENED[mode]


@pytest.mark.parametrize("mode", engine.MODES)
def test_the_runtime_from_the_box_panel_ripples_under_each_ripple_mode(running, mode):
    slack_after_the_thing(running)
    asked = {"box": running["cube"].pk, "runtime": "120", "mode": mode}
    before = evening(running)

    running["admin"].post(PREVIEW, asked)
    assert evening(running) == before
    running["admin"].post(RUNTIME, asked)

    assert evening(running)[0] == (0, 120)
    assert Suggestion.objects.get(pk=running["films"]["Cube"].pk).runtime == 120
    assert evening(running)[1:] == RUNTIME_CHANGED[mode]


def test_an_arrange_preview_in_run_shows_the_arrangement_and_writes_nothing(running):
    before = evening(running)

    previewed = running["admin"].post(PREVIEW, {"arrange": "lay-out", "minutes": "10"})

    assert previewed.status_code == 200 and evening(running) == before
    assert list(Box.objects.order_by("start").values_list("start", flat=True)) == [0, 100, 160]
    running["admin"].post(ARRANGE, {"arrange": "lay-out", "minutes": "10"})
    assert evening(running) == [(0, 90), (100, 145), (155, 264)]


def test_the_runtime_from_the_box_panel_saves_and_the_evening_follows(running):
    running["admin"].post(PREVIEW, {"box": running["cube"].pk, "runtime": "100", "mode": NONE})
    assert evening(running)[0] == (0, 90)
    running["admin"].post(RUNTIME, {"box": running["cube"].pk, "runtime": "100", "mode": NONE})

    assert evening(running)[0] == (0, 100)
    assert Suggestion.objects.get(pk=running["films"]["Cube"].pk).runtime == 100


def test_the_films_tab_corrects_a_runtime_without_rippling_in_run(running):
    running["admin"].post(FILMS_RUNTIME, {"suggestion": running["films"]["Cube"].pk, "runtime": "130", "show": "all"})

    assert evening(running) == [(0, 130), (100, 145), (160, 269)]


def test_a_film_added_by_plus_lands_after_the_last_box(running):
    running["admin"].post(ADD, {"suggestion": running["films"]["Alien"].pk})

    assert (270, 387) in evening(running)


def test_a_film_dragged_on_previews_then_saves_and_the_evening_follows(running):
    asked = {"suggestion": running["films"]["Alien"].pk, "start": "300", "mode": GAPS}
    running["admin"].post(PREVIEW, asked)
    assert len(evening(running)) == 3

    running["admin"].post(PLACE, asked)

    assert (300, 417) in evening(running)


def test_a_break_is_laid_after_the_last_box(running):
    running["admin"].post(BREAK)

    assert len(evening(running)) == 4 and max(evening(running))[1] - max(evening(running))[0] == 30


def test_swapping_a_film_removes_its_box_and_places_another(running):
    running["admin"].post(REMOVE, {"box": running["thing"].pk})
    assert evening(running) == [(0, 90), (100, 145)]

    running["admin"].post(ADD, {"suggestion": running["films"]["Alien"].pk})

    assert len(evening(running)) == 3 and not Box.objects.filter(pk=running["thing"].pk).exists()


def test_both_arrange_utilities_arm_and_apply_in_run(running):
    armed = running["admin"].get(f"{PICK}?arrange=lay-out&minutes=10")
    assert armed.status_code == 200 and evening(running) == [(0, 90), (100, 145), (160, 269)]
    running["admin"].post(ARRANGE, {"arrange": "lay-out", "minutes": "10"})
    assert evening(running) == [(0, 90), (100, 145), (155, 264)]

    running["admin"].post(ARRANGE, {"arrange": "spread"})
    assert evening(running)[0] == (0, 90) and evening(running)[-1][1] == 264


def test_the_anchor_shifts_the_evening_and_the_budget_saves(running):
    running["admin"].post(ANCHOR, {"anchor": "2026-11-07T19:00"})
    answer = running["voter"].get("/evening/", headers={"HX-Request": "true"}).text
    assert 'data-start="2026-11-07T19:00:00' in answer

    running["admin"].post(BUDGET, {"hours": "9", "minutes": "30"})
    assert Timetable.objects.get().budget == 570


def test_the_ripple_mode_is_sticky_in_run(running):
    running["admin"].post(MODE, {"mode": GAPS})

    page = running["admin"].get(PICK).text
    assert re.search(r'value="keep-gaps"[^>]*aria-pressed="true"', page)
    assert 'type="hidden" name="mode" value="keep-gaps"' in page and 'type="hidden" name="mode" value="none"' not in page


def test_the_pick_tab_is_still_the_admins_alone_in_run(running):
    assert running["voter"].post(MOVE, {"box": running["dinner"].pk, "start": "120"}).status_code in (302, 403)
    assert evening(running) == [(0, 90), (100, 145), (160, 269)]
