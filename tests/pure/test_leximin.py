"""Leximin: its key, who it counts, its distance and the level each hand-chosen trap guards (#176)."""

import pytest

from ribcage.readouts import plan, tiebreaker
from ribcage.readouts.floor import NO_BALLOT, NOTHING_REPRESENTABLE, SET_ASIDE, FloorSet
from ribcage.readouts.slate import DISREGARDED
from ribcage.solver import model
from tests.oracle import disagreements, leximin_traps

FLOOR = FloorSet(("a", "b"), (("c", NOTHING_REPRESENTABLE), ("d", NO_BALLOT), ("e", SET_ASIDE)))
RECORDS = (
    ("a", "x", 3, False, False),
    ("a", "y", None, True, False),
    ("b", "x", 1, False, False),
    ("b", "y", 2, False, False),
    ("c", "x", -1, False, False),
    ("e", "x", 3, False, False),
    ("a", "off", 3, False, False),
)


def test_the_key_is_the_counted_voters_slate_sums_lowest_first():
    assert tiebreaker.leximin(["x", "y"], RECORDS, FLOOR) == tuple(sorted([3 - 2, 1 + 2, -1]))


def test_a_voter_with_nothing_representable_counts_and_no_ballot_and_set_aside_do_not():
    assert FLOOR.counted == ("a", "b", "c")
    assert set(tiebreaker.slate_sums(["x"], RECORDS, FLOOR)) == {"a", "b", "c"}


def test_a_record_on_a_film_outside_the_slate_counts_for_nobody():
    assert tiebreaker.slate_sums(["x"], RECORDS, FLOOR) == {"a": 3, "b": 1, "c": -1}


def test_an_unsorted_film_counts_0_and_a_disregarded_veto_0():
    records = (("a", "x", None, DISREGARDED, False), ("a", "y", None, False, True), ("b", "x", None, True, False))

    assert tiebreaker.slate_sums(["x", "y"], records, FloorSet(("a", "b"), ())) == {"a": 0, "b": -2}


def test_keys_are_compared_as_tuples_so_a_higher_lowest_sum_beats_any_total():
    assert (5, 5, 5, 5, 5) > (4, 10, 10, 10, 10)
    assert (4, 6, 9) > (4, 5, 99)


def test_the_key_is_the_breakdowns_slate_sums_of_the_counted_voters_sorted():
    floor_set = FloorSet(("a", "b"), (("c", NOTHING_REPRESENTABLE),))
    slate = ["x", "y"]
    held = [each for each in RECORDS if each[1] in slate and each[0] != "e"]
    read = plan.plan(("a", "b", "c"), slate, {"x": 60, "y": 60}, held, floor_set, None)
    broken = plan.breakdown(read, slate, {"x": 60, "y": 60}, held, slate, held)

    assert tiebreaker.leximin(slate, held, floor_set) == tuple(sorted(each.slate_sum for each in broken.people))


def test_the_lowest_are_the_voters_holding_the_least_slate_sum():
    assert tiebreaker.lowest({"a": 3, "b": -1, "c": -1}) == ("b", "c")
    assert tiebreaker.lowest({}) == ()


def test_the_distance_is_the_first_place_from_the_lowest_where_the_keys_differ_and_by_how_much():
    assert tiebreaker.leximin_distance((2, 4, 9), (2, 6, 5)) == tiebreaker.Gap(2, -2)
    assert tiebreaker.leximin_distance((3, 4), (2, 9)) == tiebreaker.Gap(1, 1)
    assert tiebreaker.leximin_distance((2, 4), (2, 4)) is None


TRAPS = {each.name: each for each in leximin_traps()}
# The level each trap guards: the oracle disagrees with the solver once it is cut from `model.py`.
GUARDS = {
    "a slate the total wins but leximin loses": 1,
    "a tie the lowest slate sum leaves and the second-lowest separates": 2,
    "a voter with nothing representable whose -1 decides": 1,
    "a leximin tie with a voter with no ballot beside it": 1,
    "a disregarded veto counted as 0 in the slate sums": 1,
}


def test_every_trap_names_its_level():
    assert set(GUARDS) == set(TRAPS)


@pytest.mark.parametrize("name", GUARDS)
def test_the_solver_agrees_with_enumeration_on_each_trap(name):
    assert disagreements(TRAPS[name]) == []


@pytest.mark.parametrize("name", GUARDS)
def test_each_trap_fails_with_its_level_cut_from_the_model(name, monkeypatch):
    real = model.leximin_level
    monkeypatch.setattr(model, "leximin_level", lambda given, count: [] if count == GUARDS[name] else real(given, count))

    assert disagreements(TRAPS[name])


def test_a_voter_with_no_ballot_changes_no_answer():
    plain, with_nobody = TRAPS["a slate the total wins but leximin loses"], TRAPS["a leximin tie with a voter with no ballot beside it"]

    assert plain.records == with_nobody.records
    assert disagreements(with_nobody) == []
