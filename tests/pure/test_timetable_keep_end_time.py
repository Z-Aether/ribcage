"""Push · keep end time over plain boxes: the traps of squeezing gaps and flexible boxes to hold an edge (#13, #22, #141)."""

import random

from ribcage.timetable import engine
from ribcage.timetable.engine import Placed

END = engine.KEEP_END_TIME


def film(key, start, length):
    return Placed(key, start, length, True)


def labelled(key, start, length, flexible=False):
    return Placed(key, start, length, False, flexible)


def by_key(boxes):
    return {each.key: each for each in boxes}


def starts(boxes):
    return {each.key: each.start for each in boxes}


def lengths(boxes):
    return {each.key: each.length for each in boxes}


def test_the_gaps_give_up_the_delta_in_proportion_and_the_last_end_holds():
    # a 0–60, gap 20, b 80–140, gap 40, c 180–240. Moving a 30 later asks 30 of the 60 minutes of gap: half of each.
    evening = [film("a", 0, 60), film("b", 80, 60), film("c", 180, 60)]

    after = engine.edit(evening, "a", engine.Move(30), END)

    assert starts(after) == {"a": 30, "b": 100, "c": 180}
    assert max(each.end for each in after) == 240


def test_a_move_short_of_contact_squeezes_nothing():
    evening = [film("a", 0, 60), film("b", 80, 60)]

    assert starts(engine.edit(evening, "a", engine.Move(20), END)) == {"a": 20, "b": 80}


def edge_error(seed, lengths):
    pick = random.Random(seed)
    evening, at = [], 0
    for number in range(12):
        at += pick.choice([0, 5, 10, 15, 30, 45])
        length = pick.choice(lengths)
        evening.append(film(number, at, length))
        at += length
    edge = max(each.end for each in evening)

    after = engine.edit(evening, 0, engine.Move(pick.choice([10, 20, 35])), END)

    room = sum(each.start - previous.end for previous, each in zip(evening, evening[1:], strict=False))
    return abs(max(each.end for each in after) - edge) if room >= 35 else 0


def test_the_outer_edge_holds_within_two_and_a_half_minutes_over_many_boxes():
    assert max(edge_error(seed, [75, 90, 95, 100, 120, 125]) for seed in range(300)) <= 2.5


def test_the_outer_edge_holds_within_a_grid_step_over_many_odd_length_boxes():
    # A start that must round up past an odd film's end can cost the edge up to a step; the residue still does not run on.
    assert max(edge_error(seed, [73, 88, 94, 101, 117, 127]) for seed in range(300)) <= 5


def test_the_residue_does_not_accumulate_down_a_long_run_of_equal_gaps():
    # Twenty 60-minute films 7 minutes apart; 40 minutes are squeezed out of 133, which lands on no grid mark.
    evening = [film(number, number * 67, 60) for number in range(20)]
    edge = max(each.end for each in evening)

    after = engine.edit(evening, 0, engine.Move(40), END)

    assert abs(max(each.end for each in after) - edge) <= 2.5
    for each in after[1:]:
        assert each.start % 5 == 0


def test_every_start_is_on_the_five_minute_grid():
    evening = [film("a", 0, 60), film("b", 83, 61), film("c", 190, 59), film("d", 261, 70)]

    after = engine.edit(evening, "a", engine.Move(37), END)

    assert [each.start % 5 for each in after if each.key != "a"] == [0, 0, 0]


def test_the_squeeze_bottoms_out_at_zero_gaps_and_becomes_a_flat_push():
    # 15 minutes of gap in all; a delta of 40 pushes the last end by the 25 left over.
    evening = [film("a", 0, 60), film("b", 70, 60), film("c", 135, 60)]

    after = engine.edit(evening, "a", engine.Move(40), END)

    assert starts(after) == {"a": 40, "b": 100, "c": 160}
    assert max(each.end for each in after) == 195 + 25


def test_a_flexible_box_shrinks_alongside_the_gaps_in_proportion():
    # Gaps total 30 (10 each), Dinner can give 40: 20 of the 70 owed, 2/7 of each, so Dinner gives about 11 and each gap about 3.
    evening = [film("a", 0, 60), film("b", 70, 60), labelled("dinner", 140, 45, True), film("c", 195, 60)]
    after = engine.edit(evening, "a", engine.Move(20), END)
    placed = by_key(after)

    assert max(each.end for each in after) == 255
    assert placed["dinner"].length == 35
    assert placed["b"].start - placed["a"].end in (5, 10)


def test_a_flexible_box_never_goes_below_five_minutes():
    evening = [film("a", 0, 60), labelled("dinner", 60, 45, True), film("b", 105, 60)]

    after = engine.edit(evening, "a", engine.Move(35), END)

    assert by_key(after)["dinner"].length == 10
    after = engine.edit(evening, "a", engine.Move(500), END)
    assert by_key(after)["dinner"].length == 5


def test_past_the_slack_every_flexible_box_sits_at_five_and_the_rest_is_a_flat_push():
    evening = [film("a", 0, 60), labelled("dinner", 70, 45, True), film("b", 125, 60)]

    after = engine.edit(evening, "a", engine.Move(100), END)

    assert starts(after) == {"a": 100, "dinner": 160, "b": 165}
    assert lengths(after)["dinner"] == 5


def test_a_non_flexible_labelled_box_and_every_film_keep_their_lengths():
    evening = [film("a", 0, 60), labelled("tea", 70, 30), film("b", 110, 61), labelled("dinner", 190, 45, True), film("c", 245, 59)]

    after = engine.edit(evening, "a", engine.Move(30), END)

    kept = lengths(after)
    assert kept["tea"] == 30 and kept["b"] == 61 and kept["c"] == 59 and kept["a"] == 60


def test_the_edited_box_is_never_squeezed_by_its_own_edit():
    evening = [labelled("dinner", 0, 45, True), film("a", 50, 60)]

    after = engine.edit(evening, "dinner", engine.Resize(60), END)

    assert lengths(after)["dinner"] == 60


def test_a_longer_box_squeezes_the_gaps_after_it():
    evening = [labelled("dinner", 0, 30), film("a", 40, 60), film("b", 120, 60)]

    after = engine.edit(evening, "dinner", engine.Resize(60), END)

    assert starts(after)["a"] >= 60 and max(each.end for each in after) in range(178, 183)


def test_an_earlier_edit_holds_the_first_boxs_start():
    # Mirror of the first test: dragging c earlier pushes b and a toward the anchor's side, holding a's start.
    evening = [film("a", 0, 60), film("b", 80, 60), film("c", 180, 60)]

    after = engine.edit(evening, "c", engine.Move(150), END)

    assert min(each.start for each in after) in range(-2, 3)
    assert starts(after)["c"] == 150
    assert all(each.end <= 150 for each in after if each.key != "c")


def test_an_earlier_edit_flat_pushes_past_the_slack_and_may_cross_the_anchor():
    evening = [film("a", 0, 60), film("b", 65, 60)]

    after = engine.edit(evening, "b", engine.Move(20), END)

    assert starts(after) == {"a": -40, "b": 20}


def test_an_earlier_edit_shrinks_a_flexible_box_too():
    evening = [film("a", 0, 60), labelled("dinner", 70, 45, True), film("b", 125, 60)]

    after = engine.edit(evening, "b", engine.Move(95), END)

    assert min(each.start for each in after) in range(-2, 3)
    assert by_key(after)["dinner"].length < 45


def test_the_input_is_untouched():
    evening = [film("a", 0, 60), labelled("dinner", 70, 45, True), film("b", 125, 60)]
    kept = list(evening)

    engine.edit(evening, "a", engine.Move(30), END)

    assert evening == kept


def test_keep_gaps_and_none_leave_a_flexible_box_at_full_length():
    evening = [film("a", 0, 60), labelled("dinner", 70, 45, True), film("b", 125, 60)]

    for mode in (engine.NONE, engine.KEEP_GAPS):
        assert lengths(engine.edit(evening, "a", engine.Move(30), mode))["dinner"] == 45


def test_a_later_edit_starts_every_pushed_box_on_the_grid_after_odd_length_films():
    # 109, 94 and 101 minute films with small gaps: a start squeezed behind an odd end rounds up to the next mark.
    evening = [film("a", 0, 60), film("b", 75, 109), film("c", 199, 94), film("d", 308, 101)]

    after = engine.edit(evening, "a", engine.Move(25), END)

    assert [each.start % 5 for each in after if each.key != "a"] == [0, 0, 0]


def test_a_start_squeezed_behind_an_odd_film_end_rounds_up_to_the_next_mark():
    # b ends at 194 after the push, behind c's squeezed start: c starts at 195 on the grid rather than flush at 194.
    evening = [film("a", 10, 61), film("b", 80, 89), film("c", 170, 109), film("d", 305, 94)]

    after = engine.edit(evening, "a", engine.Move(40), END)

    assert starts(after) == {"a": 40, "b": 105, "c": 195, "d": 305}
    assert by_key(after)["d"].end == 399


def test_an_earlier_edit_rounds_the_real_starts_and_holds_the_first_start():
    evening = [film("a", 0, 109), film("b", 120, 94), film("c", 230, 101), film("d", 340, 60)]

    after = engine.edit(evening, "d", engine.Move(320), END)

    placed = by_key(after)
    assert placed["a"].start == 0
    assert [placed[key].start % 5 for key in "abc"] == [0, 0, 0]
    assert min(each.start for each in after) == 0


def test_a_flexible_box_never_goes_below_five_inside_the_squeeze():
    # The squeeze takes gaps and a 10-minute flexible box part way; rounding must not carry it under 5.
    evening = [film("a", 0, 60), labelled("tea", 60, 10, True), film("b", 90, 60), film("c", 160, 60)]

    for delta in range(5, 60, 3):
        after = engine.edit(evening, "a", engine.Move(delta), END)
        assert by_key(after)["tea"].length >= 5, delta
    after = engine.edit([film("a", 0, 60), labelled("tea", 61, 15, True), film("b", 77, 60)], "a", engine.Move(2), END)
    assert by_key(after)["tea"].length >= 5


def test_a_flexible_box_off_the_grid_after_a_typed_earlier_edit_stays_at_five_or_more():
    # b typed to start at 69 leaves tea starting off the grid; rounding its end must not take it under the 5-minute floor.
    evening = [film("a", 0, 60), labelled("tea", 80, 6, True), film("b", 86, 60)]

    after = engine.edit(evening, "b", engine.Move(69), END)

    assert by_key(after)["tea"].length >= 5


def test_an_earlier_edit_with_slack_to_spare_leaves_the_first_start_exactly_where_it_was():
    # 54 minutes of gap, 35 owed, odd runtimes: the first start holds and the later ones sit on marks.
    evening = [film(number, start, length) for number, (start, length) in enumerate([(5, 117), (130, 101), (235, 88), (340, 73), (420, 117), (555, 88)])]

    after = engine.edit(evening, 5, engine.Move(520), END)

    assert by_key(after)[0].start == 5
    assert [each.start % 5 for each in after[1:]] == [0] * 5
    assert not engine.overlaps(after)


def test_an_earlier_squeeze_never_overlaps_a_film_behind_an_odd_one():
    evening = [film(0, 15, 109), film(1, 135, 73), labelled("tea", 210, 10, True), film(3, 225, 101), film(4, 330, 88)]

    after = engine.edit(evening, 4, engine.Move(310), END)

    assert not engine.overlaps(after)


def test_a_later_squeeze_never_overlaps_a_film_behind_an_odd_one():
    evening = [film(0, 5, 117), film(1, 130, 101), labelled("tea", 235, 15, True), film(3, 250, 117), film(4, 375, 117)]

    after = engine.edit(evening, 0, engine.Move(25), END)

    assert not engine.overlaps(after)
    assert [each.start % 5 for each in after[1:4]] == [0] * 3


def test_an_earlier_edit_holds_a_flexible_first_box_where_it_was():
    evening = [labelled("tea", 3, 20, True), film("a", 28, 89), film("b", 125, 101), film("c", 240, 60)]

    after = engine.edit(evening, "c", engine.Move(210), END)

    assert (by_key(after)["tea"].start, by_key(after)["tea"].length) == (3, 12)
    assert starts(after) == {"tea": 3, "a": 15, "b": 105, "c": 210}


def test_an_earlier_squeeze_keeps_a_flexible_box_from_crowding_out_the_boxes_before_it():
    # The flexible tea's end may not pass the last mark the film before it can still start from; the first start holds.
    evening = [film("a", 5, 94), labelled("tea", 100, 30, True), film("b", 145, 73), film("c", 235, 101), film("d", 355, 88), film("e", 455, 94)]

    after = engine.edit(evening, "e", engine.Move(420), END)

    assert by_key(after)["a"].start == 5
    assert not engine.overlaps(after)
