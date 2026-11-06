"""SOLVE's pure core: the model against the objective's own value on every subset, and each solver trap (#6, #10, #11, #15, #25, #33, #165)."""

import itertools
import random
from importlib.metadata import version

import highspy
import pytest

from ribcage.readouts.floor import floor_set
from ribcage.solver import model
from ribcage.solver.model import solve
from ribcage.solver.objective import Problem, scale_of, value


def problem(runtimes, records, voters=("a", "b"), budget=None, members=None, multiplier=1, **more):
    found = floor_set(voters, runtimes, records, budget)
    if members is not None:
        found = type(found)(tuple(members), ())
    return Problem(tuple(voters), runtimes, tuple(records), budget, found, multiplier, **more)


def best_by_enumeration(given, scale=None):
    """Every subset within the budget, the best by the objective's key."""
    films = sorted(given.runtimes)
    fits = [
        frozenset(chosen)
        for size in range(len(films) + 1)
        for chosen in itertools.combinations(films, size)
        if given.budget is None or sum(given.runtimes[each] for each in chosen) <= given.budget
    ]
    return max(value(each, given, scale).key for each in fits)


def test_only_the_total_separates_two_slates_and_the_gap_is_zero(monkeypatch):
    # a is represented 2 by either film; c has seen Y, so is out of the floor set, and likes it: only T tells them apart.
    records = [("a", "x", 2, False, False), ("a", "y", 2, False, False), ("c", "y", 3, False, True), ("c", "x", 0, False, False)]
    given = problem({"x": 100, "y": 100}, records, voters=("a", "c"), budget=100)
    seen = []

    class Spy(highspy.Highs):
        def __init__(self):
            super().__init__()
            seen.append(self)

    monkeypatch.setattr(model.highspy, "Highs", Spy)

    assert solve(given) == {"y"}
    assert seen[0].getOptionValue("mip_rel_gap")[1] == 0


def test_a_scale_of_one_flips_the_winner_and_the_computed_scale_gets_it_right():
    # b, c and d have seen X and love it: T favours X while the floor and Σrep favour Y; K = 1 lets T win.
    records = [("a", "x", 1, False, False), ("a", "y", 2, False, False)] + [(each, "x", 3, False, True) for each in "bcd"]
    given = problem({"x": 100, "y": 100}, records, voters=tuple("abcd"), budget=100, tiebreaker="total")

    assert given.floor_set.members == ("a",)
    assert solve(given, scale=1) == {"x"}
    assert scale_of(given) == 2 * (1 + 2 + 9) + 1
    assert solve(given) == {"y"}


def test_a_voter_with_no_ballot_does_not_pin_the_floor_to_zero():
    # Y wins at floor 2 (9 against 8); a floor pinned to 0 by the voter with no ballot would make X win (6 against 5).
    records = [("a", "x", 1, False, False), ("b", "x", 5, False, False), ("a", "y", 3, False, False), ("b", "y", 2, False, False)]
    given = problem({"x": 90, "y": 90}, records, voters=("a", "b", "nobody"), budget=90, members=("a", "b"))

    assert solve(given) == {"y"}


def test_a_vetoed_film_counts_minus_two_in_the_total_never_zero_or_omitted():
    records = [("a", "x", 3, False, False), ("b", "x", None, True, False), ("a", "y", 1, False, False), ("b", "y", 1, False, False)]
    given = problem({"x": 60, "y": 60}, records)

    assert value({"x"}, given).total == 3 - 2
    assert value({"x", "y"}, given).total == (3 - 2) + 2
    # Y alone is worth more than X alone once the veto counts: 2 against 1, and the floor is 1 against 0.
    assert solve(problem({"x": 60, "y": 60}, records, budget=60)) == {"y"}


@pytest.mark.parametrize("barred", [(None, True, False), (3, False, True)])
def test_a_veto_and_a_seen_it_each_bar_a_film_from_representing_its_voter(barred):
    score, vetoed, seen_it = barred
    records = [("a", "x", score, vetoed, seen_it), ("a", "y", 1, False, False)]
    given = problem({"x": 60, "y": 60}, records, voters=("a",), budget=60)

    assert value({"x"}, given).floor == 0
    # Choosing X would be better for the voter's score if it could represent; it can't, so Y wins.
    assert solve(given) == {"y"}


def test_an_empty_floor_set_optimises_the_total_alone():
    records = [("a", "x", 3, False, False), ("a", "y", 1, False, False), ("b", "y", 3, False, False)]
    given = problem({"x": 60, "y": 60}, records, budget=60, members=(), tiebreaker="total")

    assert given.weight == 0
    assert value({"y"}, given).floor is None
    assert solve(given) == {"y"}


def test_no_budget_takes_every_film_that_helps():
    records = [("a", "x", 3, False, False), ("a", "y", 1, False, False), ("a", "z", None, True, False), ("b", "w", 0, False, False)]
    given = problem({"x": 500, "y": 500, "z": 500, "w": 500}, records)

    assert solve(given) == {"x", "y"}


def test_nothing_fits_gives_the_empty_slate():
    given = problem({"x": 90}, [("a", "x", 3, False, False)], budget=60)

    assert solve(given) == frozenset()
    assert value(frozenset(), given).triple == (None, 0, 0)


def test_a_found_slate_is_cut_off_and_none_when_nothing_else_is_far_enough():
    given = problem({"x": 10, "y": 10}, [("a", "x", 3, False, False), ("a", "y", 2, False, False)])

    assert solve(given) == {"x", "y"}
    assert solve(given, found=[frozenset({"x", "y"})]) in ({"x"}, {"y"}, frozenset())
    assert solve(given, found=[frozenset({"x", "y"})], distance=3) is None


def test_the_installed_highspy_is_at_least_the_first_correct_release():
    assert tuple(int(each) for each in version("highspy").split(".")[:3]) >= (1, 15, 1)


@pytest.mark.parametrize("seed", range(40))
def test_the_solver_matches_the_best_subset_by_the_objective(seed):
    chance = random.Random(seed)
    voters = tuple("abcd")
    films = {f"f{n}": chance.choice([60, 90, 120, 150]) for n in range(7)}
    records = []
    for voter in voters:
        for film in films:
            roll = chance.random()
            if roll < 0.2:
                records.append((voter, film, None, True, False))
            elif roll < 0.7:
                records.append((voter, film, chance.choice([-1, 0, 1, 2, 3]), False, chance.random() < 0.15))
    given = problem(films, records, voters=voters, budget=chance.choice([None, 200, 300, 400]), multiplier=chance.choice([1, 2]))

    chosen = solve(given)

    assert value(chosen, given).key == best_by_enumeration(given)
    assert given.budget is None or sum(films[each] for each in chosen) <= given.budget
