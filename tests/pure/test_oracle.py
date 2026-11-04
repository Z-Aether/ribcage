"""The enumeration oracle against the solver, on demand: `python -m pytest -m slow tests/pure/test_oracle.py` after changing the objective (#6, #25, #173).

The fixed cases it also writes are `python -m tests.oracle`'s to regenerate (`fixtures/solver/cases.json`).
"""

import pytest

from ribcage.readouts.basis import Basis
from ribcage.timetable import batch
from tests.oracle import KNOBS, Instance, disagreements, drawn, feasible_slates, hand_chosen, problem_of

pytestmark = pytest.mark.slow


@pytest.mark.parametrize("instance", hand_chosen(), ids=lambda each: each.name)
def test_the_solver_agrees_with_enumeration_on_the_traps_and_endings(instance):
    assert disagreements(instance) == []


@pytest.mark.parametrize("knob", KNOBS)
@pytest.mark.parametrize("seed", range(8))
def test_the_chain_agrees_with_enumeration_on_seeded_draws_under_each_knob(seed, knob):
    assert disagreements(drawn(seed, films=11, knob=knob)) == []


@pytest.mark.parametrize("seed", range(3))
def test_sixteen_films_agree_with_no_knob_and_with_every_knob(seed):
    for knob in ("none", "all"):
        assert disagreements(drawn(seed, films=16, voters=5, knob=knob)) == []


def test_the_oracle_catches_a_proposal_that_is_not_the_best(monkeypatch):
    instance = drawn(1, films=8)
    monkeypatch.setattr(batch, "chain", lambda given, length, distance: ([frozenset()], False))

    assert disagreements(instance)


def test_the_endings_name_themselves_where_enumeration_finds_nothing():
    by_name = {each.name: each for each in hand_chosen()}
    pins = problem_of(by_name["pins over the budget"])

    assert feasible_slates(pins) == []
    assert batch.ending_of(pins, [], None).startswith("The films fixed in alone exceed the budget")
    assert batch.ending_of(problem_of(by_name["nothing fits"])) == batch.NOTHING_FITS
    assert batch.ending_of(problem_of(by_name["an empty floor set"])) == batch.NO_FLOOR
    assert batch.ending_of(problem_of(by_name["no films"])) == batch.NO_FILMS
    knob = by_name["every film fixed out"]
    assert batch.ending_of(problem_of(knob), basis=Basis(fixed_out=frozenset(knob.fixed_out))) == batch.ALL_OUT
