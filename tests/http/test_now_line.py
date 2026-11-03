"""The admin's track carries a now line in RUN, where the present falls inside its scale, and never in PICK (#163)."""

import re
from datetime import timedelta

from django.utils import timezone

from ribcage.phase.history import move
from ribcage.phase.order import Phase
from ribcage.timetable.models import Timetable
from tests.http.test_pick_in_run import MOVE, PICK, PREVIEW, running  # noqa: F401



def line_of(page):
    """The now line's opening tag, or None."""
    found = re.search(r'<div class="track__now[^>]*>', page)
    return found.group(0) if found else None


def is_hidden(tag):
    return re.search(r"\shidden(\s|$)", tag) is not None


def anchor_at(minutes_ago):
    Timetable.objects.update(anchor=timezone.now() - timedelta(minutes=minutes_ago))


def test_in_run_with_the_anchor_in_the_past_the_track_carries_the_line_on_the_scale(running):
    anchor_at(30)

    tag = line_of(running["admin"].get(PICK).text)

    assert tag and not is_hidden(tag) and "--at: " in tag and 'data-anchor="' in tag and 'data-zone="' in tag


def test_with_the_anchor_ahead_the_line_is_hidden_off_the_scale(running):
    anchor_at(-3 * 24 * 60)

    tag = line_of(running["admin"].get(PICK).text)

    assert is_hidden(tag) and "--at" not in tag


def test_after_the_evening_has_ended_the_line_is_hidden_too(running):
    anchor_at(10 * 24 * 60)

    assert is_hidden(line_of(running["admin"].get(PICK).text))


def test_in_pick_there_is_no_line_at_all(running):
    anchor_at(30)
    move(Phase.RUN, Phase.PICK)

    assert line_of(running["admin"].get(PICK).text) is None
    assert "track__now" not in running["admin"].get(PICK).text


def test_a_drags_preview_keeps_the_line_on_the_held_scale(running):
    anchor_at(30)
    held = {"scale_start": "-60", "scale_length": "400"}

    preview = running["admin"].post(PREVIEW, {"box": running["dinner"].pk, "start": "120", "mode": "keep-gaps", **held}).text

    tag = line_of(preview)
    assert tag and not is_hidden(tag) and "--at: 22.5" in tag


def test_the_line_gates_nothing(running):
    anchor_at(30)

    running["admin"].post(MOVE, {"box": running["dinner"].pk, "start": "30", "mode": "none"})

    assert running["dinner"].__class__.objects.get(pk=running["dinner"].pk).start == 30


def test_near_the_right_end_the_line_turns_its_label_left_and_elsewhere_does_not(running):
    held = {"scale_start": "-60", "scale_length": "100", "box": running["dinner"].pk, "start": "120", "mode": "keep-gaps"}

    anchor_at(10)
    assert "is-late" not in line_of(running["admin"].post(PREVIEW, held).text)
    anchor_at(35)
    assert "is-late" in line_of(running["admin"].post(PREVIEW, held).text)
