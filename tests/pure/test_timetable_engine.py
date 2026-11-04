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


def test_a_move_under_none_changes_only_that_box_and_leaves_the_input_alone():
    before = list(EVENING)

    after = engine.edit(EVENING, "dinner", engine.Move(300), engine.NONE)

    assert after == [EVENING[0], labelled("dinner", 300, 45), EVENING[2]]
    assert EVENING == before


def test_a_move_before_the_anchor_gets_a_negative_start():
    after = engine.edit(EVENING, "a", engine.Move(-35), engine.NONE)

    assert after[0] == film("a", -35, 100)


def test_a_move_onto_a_neighbour_is_flagged_not_pushed_away():
    after = engine.edit(EVENING, "b", engine.Move(90), engine.NONE)

    assert [(each.first, each.second) for each in engine.overlaps(after)] == [("a", "b"), ("b", "dinner")]
    assert after[1] == EVENING[1]


def test_an_unknown_mode_or_change_is_refused():
    import pytest

    with pytest.raises(ValueError):
        engine.edit(EVENING, "a", engine.Move(5), "gaps")
    with pytest.raises(TypeError):
        engine.edit(EVENING, "a", 5, engine.NONE)


# ---------- Where the night is (#159) ----------


def states(boxes, now):
    return {key: moment.state for key, moment in engine.now_playing(boxes, now).items()}


def test_before_the_start_the_first_box_is_next_and_the_rest_later():
    assert states(EVENING, -2880) == {"a": "next", "dinner": "later", "b": "later"}
    assert engine.now_playing(EVENING, -2880)["a"].minutes_until == 2880


def test_inside_a_box_it_is_playing_with_the_minutes_left_and_the_elapsed_share_and_the_next_waits():
    short = [film("a", 0, 80), labelled("dinner", 110, 45), film("b", 170, 120)]
    found = engine.now_playing(short, 20)

    assert {key: moment.state for key, moment in found.items()} == {"a": "playing", "dinner": "later", "b": "later"}
    assert found["a"].minutes_left == 60
    assert found["a"].elapsed == 0.25


def test_a_box_starts_playing_at_its_start_and_is_past_at_its_end():
    assert states(EVENING, 0)["a"] == "playing"
    assert states(EVENING, 100)["a"] == "past"


def test_in_a_gap_the_next_box_is_next_and_the_earlier_ones_are_past():
    found = engine.now_playing(EVENING, 160)

    assert {key: moment.state for key, moment in found.items()} == {"a": "past", "dinner": "past", "b": "next"}
    assert found["b"].minutes_until == 10


def test_after_the_end_every_box_is_past():
    assert states(EVENING, 290) == {"a": "past", "dinner": "past", "b": "past"}


def test_overlapping_boxes_sharing_the_present_are_each_playing():
    assert states([film("a", 0, 100), film("b", 50, 100), film("c", 200, 30)], 60) == {"a": "playing", "b": "playing", "c": "later"}


def test_no_boxes_is_nobody_playing():
    assert engine.now_playing([], 0) == {}


def test_the_in_wording_in_minutes_hours_and_days():
    assert [engine.in_words(m) for m in (0, 0.2, 25, 25.5, 59, 60, 61, 125, 23 * 60 + 59.5, 1440, 2880, 2 * 1440 + 600)] == [
        "1m", "1m", "25m", "26m", "59m", "1h", "1h01m", "2h05m", "1 day", "1 day", "2 days", "2 days",
    ]


def test_laying_a_slate_puts_the_films_back_to_back_from_zero_in_the_order_given():
    laid = engine.lay_back_to_back([("b", 100), ("a", 90), ("c", 45)])

    assert [(each.key, each.start, each.length, each.is_film) for each in laid] == [("b", 0, 100, True), ("a", 100, 90, True), ("c", 190, 45, True)]
    assert engine.lay_back_to_back([]) == []
