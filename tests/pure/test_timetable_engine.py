"""The timetable engine over plain boxes: screen time, elapsed time, overlaps and the budget marker (#12, #22, #136)."""

from ribcage.timetable import engine
from ribcage.timetable.engine import Placed


def film(key, start, length):
    return Placed(key, start, length, True)


def labelled(key, start, length):
    return Placed(key, start, length, False)


EVENING = [film("a", 0, 100), labelled("dinner", 110, 45), film("b", 170, 120)]


def test_screen_time_counts_films_only_and_elapsed_time_counts_gaps_and_labelled_boxes():
    assert engine.screen_time(EVENING) == 220
    assert engine.elapsed_time(EVENING) == 290


def test_an_empty_evening_has_no_time_at_all():
    reading = engine.read([], 540)

    assert (reading.screen_time, reading.elapsed, reading.first_start, reading.last_end) == (0, 0, None, None)
    assert (reading.overlaps, reading.marker) == ((), None)


def test_boxes_that_only_touch_do_not_overlap():
    assert engine.overlaps([film("a", 0, 60), film("b", 60, 60)]) == ()


def test_overlaps_are_found_between_any_two_boxes_including_a_film_and_a_labelled_box():
    found = engine.overlaps([film("a", 0, 100), labelled("dinner", 90, 45), film("b", 120, 60)])

    assert [(each.first, each.second, each.start, each.end) for each in found] == [("a", "dinner", 90, 100), ("dinner", "b", 120, 135)]


def test_a_long_box_overlaps_every_box_it_spans_even_past_a_short_one_between():
    found = engine.overlaps([film("long", 0, 300), film("x", 10, 20), film("y", 100, 20), film("z", 200, 20)])

    assert {(each.first, each.second) for each in found} == {("long", "x"), ("long", "y"), ("long", "z")}


def test_overlapping_boxes_count_their_shared_minutes_in_screen_time_both_times():
    assert engine.screen_time([film("a", 0, 100), film("b", 50, 100)]) == 200


def test_the_budget_marker_lands_mid_film_where_the_budget_runs_out():
    # Films run 100 then 120 minutes with a dinner between; a budget of 150 runs out 50 minutes into the second.
    assert engine.budget_marker(EVENING, 150) == 170 + 50


def test_the_budget_marker_counts_films_in_start_order_whatever_the_order_given():
    assert engine.budget_marker(list(reversed(EVENING)), 150) == 220


def test_a_budget_met_exactly_at_a_films_end_marks_that_end_while_more_screen_time_follows():
    assert engine.budget_marker(EVENING, 100) == 100


def test_there_is_no_marker_within_the_budget_exactly_at_it_or_with_no_budget():
    assert engine.budget_marker(EVENING, 221) is None
    assert engine.budget_marker(EVENING, 220) is None
    assert engine.budget_marker(EVENING, None) is None


def test_a_box_before_the_anchor_has_a_negative_start_and_every_number_holds():
    boxes = [film("early", -90, 60), labelled("break", -20, 30), film("late", 5, 100)]

    reading = engine.read(boxes, 100)

    assert (reading.first_start, reading.last_end) == (-90, 105)
    assert (reading.screen_time, reading.elapsed) == (160, 195)
    assert [(each.first, each.second, each.start, each.end) for each in reading.overlaps] == [("break", "late", 5, 10)]
    assert reading.marker == 45
    assert reading.over == 60


def test_over_is_screen_time_less_the_budget_and_negative_when_there_is_spare():
    assert engine.read(EVENING, 240).over == -20
    assert engine.read(EVENING, 200).over == 20
    assert engine.read(EVENING, None).over is None
