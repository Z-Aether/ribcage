"""The batch's chain: the diversity cut and "more" over the pure solver (#17, #166)."""

import dataclasses
import random

import pytest

from ribcage.solver.model import solve
from ribcage.timetable.batch import chain, stopped_says
from tests.pure.test_solver import problem


def pool(seed, films=8):
    rng = random.Random(seed)
    names = [f"f{number}" for number in range(films)]
    runtimes = {name: rng.choice([60, 90, 120]) for name in names}
    records = [(voter, name, rng.choice([None, 1, 2, 3, -1]), False, False) for voter in ("a", "b", "c") for name in names]
    return problem(runtimes, records, voters=("a", "b", "c"), budget=330)


def apart(first, second):
    return len(first ^ second)


def test_every_pair_in_a_batch_differs_by_at_least_k_films_counted_both_ways():
    for seed in range(5):
        slates, _ = chain(pool(seed), 5, 4)

        assert all(apart(one, other) >= 4 for index, one in enumerate(slates) for other in slates[index + 1 :])


def test_the_first_proposal_is_the_optimum_without_the_cut():
    given = pool(1)

    assert chain(given, 5, 4)[0][0] == solve(given)


def test_more_keeps_the_first_five_and_adds_proposals_that_each_differ_from_all_before():
    given = pool(2)
    five, _ = chain(given, 5, 2)
    ten, _ = chain(given, 10, 2)

    assert ten[:5] == five and len(ten) > 5
    assert all(apart(each, before) >= 2 for index, each in enumerate(ten) for before in ten[:index])


def test_a_tiny_pool_gives_a_short_batch_with_the_cut_and_never_a_repeat():
    given = problem({"x": 10, "y": 10}, [("a", "x", 3, False, False), ("a", "y", 2, False, False)])

    slates, short = chain(given, 5, 4)

    assert slates == [frozenset({"x", "y"})] and short
    assert len(set(slates)) == len(slates)


def test_the_empty_pool_has_one_slate_and_is_short():
    slates, short = chain(problem({}, []), 5, 4)

    assert slates == [frozenset()] and short


def test_a_batch_that_fills_is_not_short():
    assert chain(pool(3), 2, 2)[1] is False


def test_the_same_inputs_give_the_same_batch_twice():
    assert chain(pool(4), 5, 3) == chain(pool(4), 5, 3)


def test_the_reason_names_the_cut():
    assert stopped_says(4) == "No other slate differs from these by 4 or more films."


def test_a_chain_resumed_from_its_kept_slates_equals_a_fresh_full_chain():
    given = pool(2)
    five, short = chain(given, 5, 2)

    assert chain(given, 10, 2, five, short) == chain(given, 10, 2)


def test_resuming_solves_only_the_proposals_still_missing(monkeypatch):
    given = pool(2)
    five, _ = chain(given, 5, 2)
    calls = []
    monkeypatch.setattr("ribcage.timetable.batch.solve", lambda *args, **kwargs: calls.append(1) or solve(*args, **kwargs))

    chain(given, 8, 2, five)
    assert len(calls) == 3

    calls.clear()
    chain(given, 5, 2, five)
    assert calls == []


def test_a_chain_that_ended_is_not_solved_again():
    given = problem({"x": 10, "y": 10}, [("a", "x", 3, False, False), ("a", "y", 2, False, False)])
    slates, short = chain(given, 5, 4)

    assert (slates, short) == ([frozenset({"x", "y"})], True)
    assert chain(given, 10, 4, slates, short) == (slates, True)


def test_a_shorter_ask_than_the_kept_slates_is_cut_to_it_and_not_short():
    given = pool(2)
    five, _ = chain(given, 5, 2)

    assert chain(given, 3, 2, five) == (five[:3], False)


def test_the_fingerprint_changes_with_anything_the_solve_reads():
    from ribcage.timetable.batch import fingerprint

    given = pool(1)
    same = fingerprint(given, 5, 4)

    assert fingerprint(pool(1), 5, 4) == same
    assert fingerprint(pool(2), 5, 4) != same
    assert fingerprint(given, 6, 4) != same and fingerprint(given, 5, 3) != same
    assert fingerprint(dataclasses.replace(given, budget=300), 5, 4) != same
    assert fingerprint(dataclasses.replace(given, multiplier=given.multiplier + 1), 5, 4) != same
    assert fingerprint(dataclasses.replace(given, tiebreaker="another"), 5, 4) != same


def test_the_fingerprint_changes_with_the_code_the_solve_runs_on(monkeypatch):
    from ribcage.timetable import batch

    given = pool(1)
    before = batch.fingerprint(given, 5, 4)
    monkeypatch.setattr(batch, "SOLVER_CODE", "another release")

    assert batch.fingerprint(given, 5, 4) != before


def test_the_code_digest_reads_the_solver_the_film_points_and_the_chain():
    from ribcage.timetable import batch

    names = {"/".join(each.parts[-2:]) for each in batch.solver_sources()}

    assert {"solver/model.py", "solver/objective.py", "readouts/slate.py", "readouts/tiebreaker.py", "timetable/batch.py"} <= names


@pytest.mark.parametrize("name", ["solver/model.py", "solver/objective.py", "readouts/slate.py", "readouts/tiebreaker.py", "timetable/batch.py"])
def test_the_code_digest_changes_when_any_file_it_reads_changes(monkeypatch, name):
    from pathlib import Path

    from ribcage.timetable import batch

    before = batch.code_digest()
    assert batch.code_digest() == before == batch.SOLVER_CODE
    read = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda self: read(self) + (b"changed" if "/".join(self.parts[-2:]) == name else b""))

    assert batch.code_digest() != before


def test_the_setting_reaches_the_problem_and_the_fingerprint(settings):
    from ribcage.timetable.batch import fingerprint, problem_of
    from tests.oracle import Instance, votes_of

    instance = Instance("one", ("a",), {"f": 60}, (("a", "f", 3, False, False),), 120)
    on, _ = votes_of(instance)
    default = problem_of(on, 1)

    settings.SLATE_TIEBREAKER = "another"
    changed = problem_of(on, 1)

    assert changed.tiebreaker == "another" != default.tiebreaker
    assert fingerprint(changed, 5, 4) != fingerprint(default, 5, 4)
