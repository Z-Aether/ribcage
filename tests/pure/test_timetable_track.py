"""The track's plain data: geometry, clock labels in TIME_ZONE, lanes and the tool row's words (#22, #36, #136)."""

from datetime import datetime, timezone as utc
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from ribcage.timetable import track
from ribcage.timetable.track import Loaded
from tests.films import a_tmdb_film

ANCHOR = datetime(2026, 11, 7, 18, 0, tzinfo=utc.utc)


def film(key, start, length, **fields):
    return Loaded(key, start, length, film=a_tmdb_film(key, f"Film {key}", runtime=length), **fields)


@pytest.mark.parametrize(("minutes", "words"), [(505, "8h25m"), (540, "9h"), (35, "35m"), (0, "0m"), (61, "1h01m")])
def test_durations_are_written_hours_and_minutes(minutes, words):
    assert track.duration(minutes) == words


def test_there_is_no_track_for_no_boxes():
    assert track.build([], ANCHOR, 540) is None


def test_the_tool_row_reads_spare_time_within_the_budget():
    built = track.build([film(1, 0, 300), Loaded(2, 300, 45, label="Dinner"), film(3, 345, 205)], ANCHOR, 540)

    tools = built.tools
    assert (tools.screen, tools.budget, tools.spare, tools.is_over) == ("8h25m", "9h", "35m to spare", False)
    assert (tools.evening, tools.elapsed, tools.overlaps) == ("Sat 18:00 → Sun 03:10", "9h10m", 0)
    assert built.marker is None


def test_the_tool_row_reads_over_and_the_marker_sits_inside_the_film_where_the_budget_runs_out():
    built = track.build([film(1, 0, 300), film(2, 310, 260)], ANCHOR, 540)

    assert (built.tools.spare, built.tools.is_over, built.tools.filled) == ("20m over", True, 100)
    assert built.marker.label == "budget 9h"
    # 240 minutes into the second film, which starts at 310 on a scale of 570 padded by 17 minutes each side.
    scale_start, scale_length = -17, 570 + 34
    assert built.marker.left == f"{(310 + 240 - scale_start) / scale_length * 100:.3f}%"


def test_with_no_budget_there_is_no_meter_spare_or_marker():
    built = track.build([film(1, 0, 600)], ANCHOR, None)

    assert (built.tools.screen, built.tools.budget, built.tools.spare, built.marker) == ("10h", None, None, None)


def test_overlapping_boxes_take_two_lanes_are_flagged_and_get_a_band():
    built = track.build([film(1, 0, 100), Loaded(2, 90, 45, label="Dinner"), film(3, 200, 60)], ANCHOR, None)

    assert [(each.box.title, each.lane, each.box.overlapping) for each in built.placements] == [("Film 1", 0, True), ("Dinner", 1, True), ("Film 3", 0, False)]
    assert (len(built.bands), built.tools.overlaps, built.lanes) == (1, 1, 2)


def test_box_times_are_wall_clock_in_the_deployments_time_zone(settings):
    settings.TIME_ZONE = "Europe/Budapest"
    timezone.activate(ZoneInfo("Europe/Budapest"))
    try:
        built = track.build([film(1, 0, 109)], ANCHOR, None)
    finally:
        timezone.deactivate()

    box = built.placements[0].box
    assert (box.starts, box.ends, box.length) == ("19:00", "20:49", "1h49m")


def test_the_axis_labels_each_hour_and_names_the_day_at_midnight():
    built = track.build([film(1, 0, 400)], ANCHOR, None)

    assert [(each.label, each.day) for each in built.ticks] == [(f"{hour % 24:02d}:00", "Sun" if hour == 24 else "") for hour in range(18, 25)]


def test_a_night_crossing_the_autumn_clock_change_shows_an_hour_twice(settings):
    zone = ZoneInfo("Europe/Budapest")
    anchor = datetime(2026, 10, 24, 22, 0, tzinfo=zone)
    timezone.activate(zone)
    try:
        built = track.build([film(1, 0, 600)], anchor, None)
    finally:
        timezone.deactivate()

    labels = [each.label for each in built.ticks]
    assert labels.count("02:00") == 2
    assert built.placements[0].box.ends == "07:00"
    assert built.tools.elapsed == "10h"


def test_a_box_before_the_anchor_lays_out_and_reads_with_its_negative_start():
    built = track.build([film(1, -90, 60), film(2, 0, 60)], ANCHOR, None)

    assert [each.box.starts for each in built.placements] == ["16:30", "18:00"]
    assert built.tools.evening == "Sat 16:30 → Sat 19:00"
    assert float(built.placements[0].left.rstrip("%")) < float(built.placements[1].left.rstrip("%"))


def test_a_long_evening_labels_fewer_hours():
    built = track.build([film(1, 0, 60), film(2, 60 * 30, 60)], ANCHOR, None)

    assert len(built.ticks) <= track.MOST_LABELS


def test_an_hour_too_near_the_right_edge_for_its_label_is_left_out():
    built = track.build([film(1, 0, 372)], ANCHOR, None)

    assert "00:00" not in [each.label for each in built.ticks]
    assert all(float(each.left.rstrip("%")) <= track.LABEL_ROOM_UNTIL for each in built.ticks)
