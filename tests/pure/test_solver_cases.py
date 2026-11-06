"""The oracle's authority at no runtime cost: the solver against the exact answers in fixtures/solver/cases.json (#25, #173).

Each case is an instance, the proposals the solver found for it and the best value enumeration found for each step, given the proposals before it.
Regenerate the file with `python -m tests.oracle`, only when the objective changes on purpose, and say so in the commit.
`tests/pure/test_oracle.py` runs enumeration afresh under `-m slow`.
"""

import json

import pytest

from ribcage.solver.model import solve
from ribcage.solver.objective import value
from tests.oracle import CASES, RULES, Instance, leximin_traps, listed, problem_of

STORED = json.loads(CASES.read_text())


def test_the_fixture_has_cases_for_the_traps_every_knob_and_both_rules():
    names = {each["instance"]["name"] for each in STORED}

    assert len(STORED) >= 30
    assert {"a floor-pinning voter", "a tie only the total separates", "a veto moves a representative", "a voter with no ballot", "pins over the budget"} <= names
    assert {each.name for each in leximin_traps()} <= names
    assert {each["instance"]["tiebreaker"] for each in STORED} == set(RULES)
    for rule in RULES:
        assert any(each["instance"]["name"].startswith("drawn-") and each["instance"]["tiebreaker"] == rule for each in STORED)
    for knob in ("without", "disregarded", "fixed_in", "fixed_out"):
        assert any(each["instance"][knob] for each in STORED)


@pytest.mark.parametrize("stored", STORED, ids=[each["instance"]["name"] for each in STORED])
def test_the_solver_and_the_objective_match_the_enumerated_answer(stored):
    instance = Instance.decoded(stored["instance"])
    problem = problem_of(instance)
    slates = [frozenset(each["films"]) for each in stored["steps"]]

    for place, step in enumerate(stored["steps"]):
        assert list(value(slates[place], problem).triple) == step["triple"]
        best = solve(problem, found=slates[:place], distance=instance.distance)
        assert listed(value(best, problem).key) == step["best"]
    after = solve(problem, found=slates, distance=instance.distance)
    if stored["exhausted"]:
        assert after is None or after in slates
    else:
        assert len(slates) == instance.length
