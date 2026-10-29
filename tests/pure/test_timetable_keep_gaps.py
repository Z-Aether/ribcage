"""Push · keep gaps over plain boxes: the traps of a push by the edit's delta (#13, #22, #140)."""

import pytest

from ribcage.timetable import engine
from ribcage.timetable.engine import Placed


def film(key, start, length):
    return Placed(key, start, length, True)


def labelled(key, start, length, flexible=False):
    return Placed(key, start, length, False, flexible)


# a 0–60, gap 10, b 70–130, gap 20, c 150–200.
EVENING = [film("a", 0, 60), film("b", 70, 60), film("c", 150, 50)]


def starts(boxes):
    return {each.key: each.start for each in boxes}


def gaps(boxes):
    ordered = engine.in_start_order(boxes)
    return [after.start - before.end for before, after in zip(ordered, ordered[1:])]


def test_a_push_is_by_the_delta_not_the_overlap_so_every_gap_is_kept():
    # a ends at 80 after +20, over b by 10 only, yet b and c both move the full 20.
    after = engine.edit(EVENING, "a", engine.Move(20), engine.KEEP_GAPS)

    assert starts(after) == {"a": 20, "b": 90, "c": 170}
    assert gaps(after) == gaps(EVENING)


def test_a_move_short_of_contact_pushes_nothing_and_eats_the_gap():
    assert starts(engine.edit(EVENING, "a", engine.Move(5), engine.KEEP_GAPS)) == {"a": 5, "b": 70, "c": 150}
    # Touching is no contact either: the boxes share no minute.
    assert starts(engine.edit(EVENING, "a", engine.Move(10), engine.KEEP_GAPS)) == {"a": 10, "b": 70, "c": 150}
    assert starts(engine.edit(EVENING, "a", engine.Move(11), engine.KEEP_GAPS)) == {"a": 11, "b": 81, "c": 161}


def test_a_push_takes_only_the_boxes_from_the_old_start_on():
    after = engine.edit(EVENING, "b", engine.Move(100), engine.KEEP_GAPS)

    assert starts(after) == {"a": 0, "b": 100, "c": 180}


def test_an_earlier_push_carries_boxes_before_the_anchor_with_no_clamp():
    evening = [film("a", 0, 60), film("b", 70, 60)]

    after = engine.edit(evening, "b", engine.Move(40), engine.KEEP_GAPS)

    assert starts(after) == {"a": -30, "b": 40}


def test_an_earlier_move_short_of_contact_pushes_nothing_and_leaves_later_boxes():
    after = engine.edit(EVENING, "c", engine.Move(135), engine.KEEP_GAPS)

    assert starts(after) == {"a": 0, "b": 70, "c": 135}


def test_an_earlier_push_leaves_the_boxes_after_alone():
    after = engine.edit(EVENING, "b", engine.Move(50), engine.KEEP_GAPS)

    assert starts(after) == {"a": -20, "b": 50, "c": 150}


def test_dragging_back_does_not_undo_a_push_since_the_reverse_move_clashes_with_nothing():
    pushed = engine.edit(EVENING, "a", engine.Move(20), engine.KEEP_GAPS)

    back = engine.edit(pushed, "a", engine.Move(0), engine.KEEP_GAPS)

    assert starts(back) == {"a": 0, "b": 90, "c": 170}


def test_a_longer_labelled_box_pushes_the_boxes_after_it_by_the_extra_length():
    evening = [labelled("dinner", 0, 30), film("b", 40, 60), film("c", 120, 50)]

    after = engine.edit(evening, "dinner", engine.Resize(60), engine.KEEP_GAPS)

    assert starts(after) == {"dinner": 0, "b": 70, "c": 150}
    assert after[0].length == 60


def test_a_longer_box_short_of_contact_pushes_nothing_and_a_shorter_one_never_does():
    evening = [labelled("dinner", 0, 30), film("b", 40, 60)]

    assert starts(engine.edit(evening, "dinner", engine.Resize(40), engine.KEEP_GAPS)) == {"dinner": 0, "b": 40}
    assert starts(engine.edit(evening, "dinner", engine.Resize(10), engine.KEEP_GAPS)) == {"dinner": 0, "b": 40}


def test_flexible_boxes_keep_their_full_length_when_pushed():
    evening = [film("a", 0, 60), labelled("tea", 70, 30, flexible=True), film("c", 100, 50)]

    after = engine.edit(evening, "a", engine.Move(30), engine.KEEP_GAPS)

    assert [(each.key, each.start, each.length) for each in after] == [("a", 30, 60), ("tea", 100, 30), ("c", 130, 50)]


def test_a_push_alone_never_touches_the_input_and_none_still_pushes_nothing():
    before = list(EVENING)

    engine.edit(EVENING, "a", engine.Move(20), engine.KEEP_GAPS)

    assert EVENING == before
    assert starts(engine.edit(EVENING, "a", engine.Move(20), engine.NONE)) == {"a": 20, "b": 70, "c": 150}


def test_a_resize_under_none_changes_that_box_alone():
    after = engine.edit([labelled("x", 0, 30), film("b", 40, 60)], "x", engine.Resize(60), engine.NONE)

    assert [(each.start, each.length) for each in after] == [(0, 60), (40, 60)]


def test_every_mode_is_acted_on():
    assert set(engine.MODES) == set(engine.RIPPLE_MODES) == {engine.NONE, engine.KEEP_GAPS}
    with pytest.raises(ValueError):
        engine.edit(EVENING, "a", engine.Move(5), "squeeze")
