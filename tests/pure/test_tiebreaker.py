"""The tiebreaker seam: a rule is a name in the readouts' keys and in the solver's levels, never one without the other (#175)."""

import pytest

from ribcage.readouts import ledger, tiebreaker
from ribcage.readouts.floor import FloorSet
from ribcage.solver import model
from ribcage.solver.objective import Problem, value

RECORDS = (("a", "x", 3, False, False), ("a", "y", None, True, False), ("b", "x", 1, False, False), ("b", "y", 2, False, False))


def test_every_rule_has_its_key_and_its_levels_and_neither_alone():
    assert set(tiebreaker.KEYS) == set(model.LEVELS)
    assert tiebreaker.DEFAULT in tiebreaker.KEYS


def test_the_totals_key_is_the_ledgers_total():
    assert tiebreaker.KEYS["total"](["x", "y"], RECORDS) == ledger.total(["x", "y"], RECORDS) == (3 + 1) + (-2 + 2)


def test_a_value_is_compared_on_floor_and_sigma_rep_then_the_rules_key():
    given = Problem(("a", "b"), {"x": 60, "y": 60}, RECORDS, 120, FloorSet(("a", "b"), ()), 1)

    both = value({"x", "y"}, given)

    assert both.key == (both.floor * both.weight + both.sigma_rep, both.total)
    assert value({"x"}, given).key[0] == value({"x"}, given).floor * both.weight + value({"x"}, given).sigma_rep


def test_a_problem_names_the_default_rule_unless_told_another():
    given = Problem((), {}, (), None, FloorSet((), ()), 1)

    assert given.tiebreaker == "total"


def test_an_unknown_rule_has_no_levels():
    given = Problem(("a",), {"x": 60}, RECORDS[:1], 60, FloorSet(("a",), ()), 1, tiebreaker="sum")

    with pytest.raises(KeyError):
        model.solve(given)
