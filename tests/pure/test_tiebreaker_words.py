"""The rule's own readouts on Compare: the column's figure and distance in words, the breakdown line and the swap row (#177)."""

import pytest

from ribcage.readouts import plan, tiebreaker
from ribcage.readouts.floor import NO_BALLOT, NOTHING_REPRESENTABLE, SET_ASIDE, FloorSet

LEXIMIN = tiebreaker.COLUMNS["leximin"]
TOTAL = tiebreaker.COLUMNS["total"]


def test_every_rule_has_its_column_beside_its_key():
    assert set(tiebreaker.COLUMNS) == set(tiebreaker.KEYS)


@pytest.mark.parametrize("place, word", [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"), (12, "12th"), (13, "13th"), (21, "21st"), (22, "22nd"), (101, "101st"), (111, "111th")])
def test_places_are_worded_as_ordinals(place, word):
    assert tiebreaker.ordinal(place) == word


def test_the_distance_names_the_first_place_from_the_lowest_where_the_rows_differ():
    assert LEXIMIN.distance((4, 5, 5, 7), (5, 5, 6, 7)) == "−1 at 1st"
    assert LEXIMIN.distance((5, 4, 5, 7), (5, 5, 6, 7)) == "−1 at 2nd"
    assert LEXIMIN.distance((5, 5, 7, 7), (5, 5, 6, 7)) == "+1 at 3rd"


def test_a_difference_only_at_the_last_position_is_named_there():
    assert LEXIMIN.distance((4, 5, 5, 6), (4, 5, 5, 9)) == "−3 at 4th"


def test_rows_equal_throughout_read_level():
    assert LEXIMIN.distance((4, 5, 5, 7), (4, 5, 5, 7)) == "="
    assert LEXIMIN.distance((), ()) == "="


def test_the_column_shows_the_lowest_slate_sum_and_the_breakdown_the_sorted_sums():
    assert (LEXIMIN.header, LEXIMIN.value((4, 5, 5, 7)), LEXIMIN.line((4, 5, 5, 7)), LEXIMIN.swap((4, 5, 5, 7))) == ("Leximin", "4", "leximin 4 · 5 · 5 · 7", "4 · 5 · 5 · 7")
    assert LEXIMIN.value(()) == "–" and LEXIMIN.line(()) == ""


def test_the_total_keeps_its_figure_and_signed_distance_and_adds_no_line_or_row():
    assert (TOTAL.header, TOTAL.value(12), TOTAL.distance(10, 12), TOTAL.distance(12, 12), TOTAL.line(12), TOTAL.swap) == ("Total", "12", "−2", "=", "", None)


def test_only_leximin_marks_the_lowest():
    assert LEXIMIN.marks_lowest and not TOTAL.marks_lowest


def test_the_breakdowns_worst_served_is_the_voter_leximin_ranks_lowest_a_nothing_representable_voter_included():
    floor_set = FloorSet(("a", "b"), (("c", NOTHING_REPRESENTABLE), ("d", NO_BALLOT), ("e", SET_ASIDE)))
    slate = ["x", "y"]
    records = [("a", "x", 3, False, False), ("b", "x", 2, False, False), ("c", "y", None, True, False), ("d", "x", 0, False, False)]
    runtimes = {"x": 60, "y": 60}
    read = plan.plan(("a", "b", "c", "d", "e"), slate, runtimes, records, floor_set, None)

    people = {each.voter: each for each in plan.breakdown(read, slate, runtimes, records, slate, records).people}
    sums = tiebreaker.slate_sums(slate, records, floor_set)

    assert sums == {"a": 3, "b": 2, "c": -2}
    assert [voter for voter, each in people.items() if each.served == "worst"] == list(tiebreaker.lowest(sums)) == ["c"]
    assert people["a"].served == "best"
    assert people["d"].served == people["e"].served == ""
