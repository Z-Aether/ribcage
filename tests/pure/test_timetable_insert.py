"""An inserted film's box goes through the ripple mode like any edit (#13, #22, #144)."""

from ribcage.timetable import engine
from ribcage.timetable.engine import Placed

NEW = "new"


def film(key, start, length):
    return Placed(key, start, length, True)


# a 0–60, gap 10, b 70–130, gap 20, c 150–200.
EVENING = [film("a", 0, 60), film("b", 70, 60), film("c", 150, 50)]


def starts(boxes):
    return {each.key: each.start for each in boxes}


def test_an_insert_adds_its_box_at_its_start_and_length_in_every_mode():
    for mode in engine.MODES:
        after = engine.edit(EVENING, NEW, engine.Insert(200, 30), mode)
        assert starts(after) == {"a": 0, "b": 70, "c": 150, NEW: 200}
        assert next(each for each in after if each.key == NEW).length == 30


def test_an_insert_under_none_only_overlaps():
    after = engine.edit(EVENING, NEW, engine.Insert(100, 60), engine.NONE)

    assert starts(after) == {"a": 0, "b": 70, "c": 150, NEW: 100}
    assert {(each.first, each.second) for each in engine.overlaps(after)} == {("b", NEW), (NEW, "c")}


def test_an_insert_in_a_gap_short_of_contact_pushes_nothing_and_touching_is_no_contact():
    for mode in (engine.KEEP_GAPS, engine.KEEP_END_TIME):
        assert starts(engine.edit(EVENING, NEW, engine.Insert(60, 5), mode)) == {"a": 0, "b": 70, "c": 150, NEW: 60}
        assert starts(engine.edit(EVENING, NEW, engine.Insert(60, 10), mode)) == {"a": 0, "b": 70, "c": 150, NEW: 60}


def test_an_insert_under_keep_gaps_pushes_the_boxes_after_it_by_its_reach_past_the_contact():
    # 60–80 reaches 10 past b's start.
    after = engine.edit(EVENING, NEW, engine.Insert(60, 20), engine.KEEP_GAPS)

    assert starts(after) == {"a": 0, NEW: 60, "b": 80, "c": 160}


def test_an_insert_onto_a_film_moves_that_film_to_where_the_insert_ends_and_everything_after_with_it():
    after = engine.edit(EVENING, NEW, engine.Insert(100, 30), engine.KEEP_GAPS)

    # b started at 70; the insert ends at 130, so b and c both move 60.
    assert starts(after) == {"a": 0, "b": 130, "c": 210, NEW: 100}


def test_an_insert_at_a_boxs_own_start_pushes_it_by_the_whole_insert():
    assert starts(engine.edit(EVENING, NEW, engine.Insert(70, 40), engine.KEEP_GAPS)) == {"a": 0, "b": 110, "c": 190, NEW: 70}


def test_an_insert_under_keep_end_time_takes_the_push_out_of_the_gaps_and_holds_the_last_end():
    after = engine.edit(EVENING, NEW, engine.Insert(60, 20), engine.KEEP_END_TIME)

    assert starts(after) == {"a": 0, NEW: 60, "b": 80, "c": 150}
    assert max(each.end for each in after if each.key != NEW) == 200


def test_an_insert_pushes_only_later_boxes_never_earlier_ones():
    after = engine.edit(EVENING, NEW, engine.Insert(-40, 50), engine.KEEP_GAPS)

    assert starts(after) == {"a": 10, "b": 80, "c": 160, NEW: -40}
