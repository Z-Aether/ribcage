"""The arrange utilities over plain boxes: lay out with a break and spread evenly (#22, #145)."""

import pytest

from ribcage.timetable import engine
from ribcage.timetable.engine import Placed


def box(key, start, length, flexible=False):
    return Placed(key, start, length, True, flexible)


def starts(boxes):
    return {each.key: each.start for each in boxes}


EVENING = [box("c", 300, 90), box("a", 0, 100), box("b", 120, 45, flexible=True), Placed("d", 200, 30, False)]


def test_lay_out_puts_every_box_back_to_back_from_the_anchor_with_the_break_between():
    laid = engine.arrange(EVENING, engine.LAY_OUT, 10)

    assert starts(laid) == {"a": 0, "b": 110, "d": 165, "c": 205}


def test_lay_out_with_no_break_is_flush_and_returns_the_boxes_in_the_order_given():
    laid = engine.arrange(EVENING, engine.LAY_OUT, 0)

    assert [each.key for each in laid] == ["c", "a", "b", "d"]
    assert starts(laid) == {"a": 0, "b": 100, "d": 145, "c": 175}


def test_spread_shares_the_empty_time_equally_on_the_grid_ending_at_the_last_end():
    # 100 + 45 + 30 + 90 = 265 of 390: 125 spare over 3 gaps.
    spread = engine.arrange(EVENING, engine.SPREAD)

    assert starts(spread) == {"a": 0, "b": 140, "d": 230, "c": 300}
    assert max(each.end for each in spread) == 390


def test_spread_keeps_every_start_on_the_grid_when_the_lengths_do_not_disturb_it():
    boxes = [box(1, 0, 60), box(2, 77, 60), box(3, 150, 60), box(4, 233, 60)]

    spread = engine.arrange(boxes, engine.SPREAD)

    assert all(each.start % 5 == 0 for each in spread)
    assert max(each.end for each in spread) in range(290, 296)


def test_spread_gives_zero_gaps_when_the_boxes_do_not_fit():
    boxes = [box("a", 0, 100), box("b", 50, 100), box("c", 60, 100)]

    assert starts(engine.arrange(boxes, engine.SPREAD)) == {"a": 0, "b": 100, "c": 200}


def test_spread_never_lets_a_rounded_start_run_into_the_box_before():
    boxes = [box(1, 0, 61), box(2, 70, 61), box(3, 140, 61), box(4, 160, 61)]

    spread = sorted(engine.arrange(boxes, engine.SPREAD), key=lambda each: each.start)

    assert all(first.end <= second.start for first, second in zip(spread, spread[1:]))


@pytest.mark.parametrize("utility", [engine.LAY_OUT, engine.SPREAD])
def test_both_keep_start_order_and_full_lengths_flexible_boxes_included(utility):
    arranged = engine.arrange(EVENING, utility, 15)

    assert {each.key: each.length for each in arranged} == {each.key: each.length for each in EVENING}
    assert [each.key for each in sorted(arranged, key=lambda each: each.start)] == ["a", "b", "d", "c"]
    assert all(after.flexible == before.flexible for before, after in zip(EVENING, arranged))


@pytest.mark.parametrize("utility", [engine.LAY_OUT, engine.SPREAD])
def test_boxes_starting_together_keep_the_order_given_so_a_result_is_the_same_each_call(utility):
    tied = [box("x", 10, 30), box("y", 10, 30), box("z", 10, 30)]

    first = engine.arrange(tied, utility, 5)

    assert [each.key for each in sorted(first, key=lambda each: each.start)] == ["x", "y", "z"]
    assert engine.arrange(tied, utility, 5) == first


def test_one_box_or_none_is_laid_from_the_anchor():
    assert starts(engine.arrange([box("a", 40, 60)], engine.SPREAD)) == {"a": 0}
    assert engine.arrange([], engine.LAY_OUT, 15) == []


def test_an_unknown_utility_is_refused():
    with pytest.raises(ValueError):
        engine.arrange(EVENING, "shuffle")


def test_spread_keeps_every_start_on_the_grid_when_the_boxes_fit_with_a_little_spare():
    # Three 97s from 0 to 292: 1 spare. A rounded start behind the last end moves up to the next mark, never off the grid.
    spread = engine.arrange([box("a", 0, 97), box("b", 97, 97), box("c", 195, 97)], engine.SPREAD)

    assert starts(spread) == {"a": 0, "b": 100, "c": 200}
