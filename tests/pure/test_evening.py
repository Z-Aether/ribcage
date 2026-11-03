"""The evening's build: the fitted scale, labels in TIME_ZONE, and none of the admin's readouts (#155)."""

from datetime import datetime, timezone

import pytest

from ribcage.timetable import evening
from ribcage.timetable.track import Loaded

ANCHOR = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)


class Film:
    def __init__(self, title):
        self.title = title
        self.poster_path = ""
        self.year = 2000


def film_box(key, start, length, title="A film", **fields):
    return Loaded(key, start, length, film=Film(title), **fields)


def test_nothing_to_show_with_no_boxes_or_no_anchor():
    assert evening.build([], ANCHOR).empty
    assert evening.build([film_box(1, 0, 90)], None).empty
    assert evening.build([], None).starts_at == ""


def test_the_scale_fits_the_first_start_to_the_last_end_and_each_box_sits_by_its_minutes():
    shown = evening.build([film_box(1, 0, 100), Loaded(2, 100, 50, label="Dinner"), film_box(3, 300, 100)], ANCHOR)

    assert shown.minutes == 400
    tops_and_heights = [(slot.top, slot.height) for slot in shown.slots]
    assert tops_and_heights == [("0.000%", "25.000%"), ("25.000%", "12.500%"), ("75.000%", "25.000%")]
    assert {slot.left for slot in shown.slots} == {"0.000%"} and {slot.width for slot in shown.slots} == {"100.000%"}


def test_the_scale_starts_at_the_first_box_even_when_a_push_carried_it_before_the_anchor():
    shown = evening.build([film_box(1, -30, 60), film_box(2, 30, 30)], ANCHOR)

    assert shown.minutes == 90
    assert shown.slots[0].top == "0.000%"
    assert shown.starts_at == "2026-11-07T17:30:00+00:00" and shown.ends_at == "2026-11-07T19:00:00+00:00"


def test_each_box_and_the_span_carry_their_instants():
    shown = evening.build([film_box(1, 10, 60)], ANCHOR)

    assert (shown.slots[0].starts_at, shown.slots[0].ends_at) == ("2026-11-07T18:10:00+00:00", "2026-11-07T19:10:00+00:00")
    assert (shown.starts_at, shown.ends_at) == (shown.slots[0].starts_at, shown.slots[0].ends_at)


def test_labels_are_in_the_time_zone_across_midnight(settings):
    settings.TIME_ZONE = "Europe/Budapest"

    shown = evening.build([film_box(1, 330, 95)], ANCHOR)

    # 18:00 UTC is 19:00 in Budapest; 5h30 on, 00:30 the next day, to 02:05.
    assert (shown.slots[0].box.starts, shown.slots[0].box.ends) == ("00:30", "02:05")


def test_labels_across_a_clock_change_show_an_hour_twice(settings):
    settings.TIME_ZONE = "Europe/Budapest"
    # The clocks go back at 03:00 on 2026-10-25: 00:30 UTC on the 25th is 02:30 CEST, and an hour on 02:30 CET again.
    anchor = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)

    shown = evening.build([film_box(1, 30, 60), film_box(2, 90, 60)], anchor)

    assert [(slot.box.starts, slot.box.ends) for slot in shown.slots] == [("02:30", "02:30"), ("02:30", "03:30")]


def test_no_strips_vetoers_dropped_mark_or_overlap_mark():
    crowded = [
        film_box(1, 0, 100, vetoed_by="SZ", vetoers="Vetoed by Sam, Zoe", veto_voters=frozenset({1, 2})),
        film_box(2, 50, 100, dropped=True),
    ]

    shown = evening.build(crowded, ANCHOR)

    for slot in shown.slots:
        box = slot.box
        assert (box.vetoed_by, box.vetoers, box.dropped, box.overlapping) == ("", "", False, False)


def test_a_flexible_box_is_drawn_without_the_flexible_arrow():
    shown = evening.build([Loaded(1, 0, 45, label="Dinner", flexible=True)], ANCHOR)

    assert shown.slots[0].box.flexible is False


def test_overlapping_boxes_share_the_width_in_columns():
    shown = evening.build([film_box(1, 0, 100), film_box(2, 50, 100), film_box(3, 100, 50)], ANCHOR)

    assert [(slot.left, slot.width) for slot in shown.slots] == [("0.000%", "50.000%"), ("50.000%", "50.000%"), ("0.000%", "50.000%")]


def test_a_dropped_film_is_an_ordinary_box():
    same = Film("Cube")
    dropped = evening.build([Loaded(1, 0, 90, film=same, dropped=True)], ANCHOR).slots[0].box
    ordinary = evening.build([Loaded(1, 0, 90, film=same)], ANCHOR).slots[0].box

    assert dropped == ordinary
