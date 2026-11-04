"""The enumeration oracle: SOLVE's answers against every slate within the budget, scored by the solver's own objective (#6, #25, #173).

An `Instance` is plain data (voters, runtimes, records, budget, knobs), so a later harness can build one from real votes: `problem_of(instance)` is the `Problem` the batch would solve.
Ties are compared by objective value, never by film set.
It cannot enumerate long budgets: past about 16 films or 12 hours it falls off a cliff (#6).

Regenerate `fixtures/solver/cases.json` with `python -m tests.oracle`, and only when the objective or a hand-chosen case changes on purpose; say which in the commit.
`tests/pure/test_solver_cases.py` reads it in the default run; `tests/pure/test_oracle.py` runs the oracle afresh under `-m slow`.
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path

from ribcage.readouts.basis import Basis
from ribcage.readouts.floor import floor_set
from ribcage.readouts.ledger import stored_votes
from ribcage.solver.objective import value
from ribcage.timetable import batch

CASES = Path(__file__).resolve().parent.parent / "fixtures" / "solver" / "cases.json"
KNOBS = ("none", "without", "disregarded", "fixed_in", "fixed_out", "all")


@dataclass(frozen=True)
class Instance:
    name: str
    voters: tuple
    runtimes: dict
    records: tuple  # (voter, film, score, vetoed, seen_it)
    budget: int  # or None
    multiplier: int = 1
    without: tuple = ()
    disregarded: tuple = ()
    fixed_in: tuple = ()
    fixed_out: tuple = ()
    distance: int = 4
    length: int = 5

    def encoded(self):
        return {**self.__dict__, "records": [list(each) for each in self.records]}

    @classmethod
    def decoded(cls, data):
        tuples = ("voters", "without", "disregarded", "fixed_in", "fixed_out")
        return cls(**{**data, **{key: tuple(data[key]) for key in tuples}, "records": tuple(tuple(each) for each in data["records"])})


def votes_of(instance):
    """The stored votes and the basis for `instance`, through the ledger's loader, so the knobs reach the solver as they do in the app (#167, #168)."""
    basis = Basis(frozenset(instance.without), frozenset(instance.disregarded), frozenset(instance.fixed_in), frozenset(instance.fixed_out))
    found = floor_set(instance.voters, instance.runtimes, instance.records, instance.budget, basis.without, basis.fixed_out)
    titles = {film: str(film) for film in instance.runtimes}
    return stored_votes(instance.voters, found, instance.records, titles, instance.runtimes, set(titles), instance.budget, basis), basis


def problem_of(instance):
    """The `Problem` the batch solves for `instance`, through `votes_of` and the batch's own `problem_of` (#167, #168)."""
    on, basis = votes_of(instance)
    return batch.problem_of(on, instance.multiplier, basis)


def feasible_slates(problem):
    """Every film set within the budget holding the films fixed in, each with its objective's integer."""
    films = sorted(problem.runtimes)
    pinned = set(problem.fixed_in)
    found = []

    def walk(index, chosen, used):
        if index == len(films):
            if pinned <= chosen:
                found.append(chosen)
            return
        film = films[index]
        if problem.budget is None or used + problem.runtimes[film] <= problem.budget:
            walk(index + 1, chosen | {film}, used + problem.runtimes[film])
        if film not in pinned:
            walk(index + 1, chosen, used)

    walk(0, frozenset(), 0)
    return [(each, value(each, problem).integer) for each in found]


def best_far_from(slates, before, distance):
    """The best integer among `slates` at least `distance` films from every slate in `before`, or None where there is none."""
    return max((integer for each, integer in slates if all(len(each ^ other) >= distance for other in before)), default=None)


def disagreements(instance, slates=None):
    """What differs between the solver's batch for `instance` and enumeration, as sentences; empty where they agree.

    Each proposal's value is held to the best slate at least `distance` films from the solver's own earlier ones, so a tie broken the other way cannot count against it.
    """
    problem = problem_of(instance)
    every = feasible_slates(problem) if slates is None else slates
    proposals, short = batch.chain(problem, instance.length, instance.distance)
    said = []
    for place, each in enumerate(proposals):
        best = best_far_from(every, proposals[:place], instance.distance)
        got = value(each, problem).integer
        if best is None:
            said.append(f"proposal {place + 1} should not exist")
        elif got != best:
            said.append(f"proposal {place + 1} is worth {got}, the best is {best}")
    after = best_far_from(every, proposals, instance.distance)
    if len(proposals) < instance.length and after is not None:
        said.append(f"the chain stopped after {len(proposals)} but a slate worth {after} is far enough")
    if short != (len(proposals) < instance.length):
        said.append(f"the chain of {len(proposals)} was reported {'short' if short else 'full'}")
    return said


def drawn(seed, films=10, voters=4, knob="none"):
    """A plain seeded random instance: runtimes, scores, vetoes and seen-its by chance, then the budget and the knob."""
    chance = random.Random(seed)
    names = [f"f{number:02d}" for number in range(films)]
    people = tuple("abcdefgh"[:voters])
    runtimes = {name: chance.choice([60, 90, 100, 120, 150]) for name in names}
    records = []
    for voter in people:
        for name in names:
            roll = chance.random()
            if roll < 0.15:
                records.append((voter, name, None, True, False))
            elif roll < 0.7:
                records.append((voter, name, chance.choice([-1, 0, 1, 2, 3]), False, chance.random() < 0.15))
    total = sum(runtimes.values())
    budget = chance.choice([None, total // 4, total // 2])
    pinned = tuple(chance.sample(names, 1)) if knob in ("fixed_in", "all") else ()
    out = tuple(each for each in chance.sample(names, 2) if each not in pinned) if knob in ("fixed_out", "all") else ()
    return Instance(
        f"drawn-{seed}-{knob}",
        people,
        runtimes,
        tuple(records),
        budget,
        chance.choice([1, 2]),
        without=tuple(chance.sample(people, 1)) if knob in ("without", "all") else (),
        disregarded=tuple(chance.sample(people, 2)) if knob in ("disregarded", "all") else (),
        fixed_in=pinned,
        fixed_out=out,
    )


def scored(voter, film, score):
    return (voter, film, score, False, False)


def case(name, *records, voters=("a", "b"), runtimes=None, budget=None, **knobs):
    return Instance(name, voters, {"x": 60, "y": 60, "z": 60} if runtimes is None else runtimes, records, budget, **knobs)


def hand_chosen():
    """The traps and the endings, each small enough to enumerate in a blink (#6, #173)."""
    return [
        # c is held to 1 by y alone: the floor wants y though x is worth more to a and b, so only the floor term picks y.
        case("a floor-pinning voter", scored("a", "x", 2), scored("a", "y", 1), scored("b", "x", 2), scored("b", "y", 1), scored("c", "y", 1), voters=("a", "b", "c"), budget=60),
        # c has seen y: only the total tells x and y apart.
        case("a tie only the total separates", scored("a", "x", 2), scored("a", "y", 2), ("c", "y", 3, False, True), scored("c", "x", 0), voters=("a", "c"), budget=60),
        # a's veto on x leaves y as a's representative: Σrep wants y, while c's seen 3 makes the total want x.
        case("a veto moves a representative", ("a", "x", None, True, False), scored("a", "y", 3), scored("b", "x", 2), scored("b", "y", -1), ("c", "x", 3, False, True), voters=("a", "b", "c"), budget=60),
        case("a disregarded veto", scored("a", "x", 3), scored("a", "y", 2), ("b", "x", None, True, False), scored("b", "y", 1), budget=60, disregarded=("b",)),
        # "nobody" is no floor member: counted as one, the floor would be 0 and x would win over the floor-pinning y.
        case("a voter with no ballot", scored("a", "x", 2), scored("a", "y", 1), scored("b", "x", 2), scored("b", "y", 1), scored("c", "y", 1), voters=("a", "b", "c", "nobody"), budget=60),
        case("an empty floor set", scored("a", "x", 3), scored("a", "y", 2), scored("b", "y", 3), budget=120, without=("a", "b")),
        case("no budget", scored("a", "x", 3), scored("a", "y", 2), scored("b", "z", 3)),
        case("nothing fits", scored("a", "x", 3), scored("a", "y", 2), runtimes={"x": 90, "y": 100}, budget=60),
        case("pins over the budget", scored("a", "x", 3), scored("a", "y", 2), scored("b", "z", 3), budget=100, fixed_in=("x", "y")),
        case("pins that fit", scored("a", "x", 3), scored("a", "y", 2), scored("b", "z", 3), budget=120, fixed_in=("z",)),
        case("every film fixed out", scored("a", "x", 3), scored("a", "y", 2), runtimes={"x": 60, "y": 60}, budget=120, fixed_out=("x", "y")),
        case("the one film that represents fixed out", scored("a", "x", 3), scored("a", "y", 2), runtimes={"x": 60, "y": 60}, fixed_out=("x",)),
        case("no films", runtimes={}, budget=120),
    ]


def cases(seeds=range(6), films=8):
    """What the generator solves: the hand-chosen instances and seeded draws under each knob kind."""
    return hand_chosen() + [drawn(seed, films=films, knob=knob) for seed in seeds for knob in KNOBS]


def solved(instance):
    """The case for the fixture: `instance`, the solver's batch and, for each proposal, the exact best value the oracle found for it.

    Raises where the solver and enumeration disagree, so a wrong answer is never written down as a right one.
    """
    problem = problem_of(instance)
    every = feasible_slates(problem)
    if said := disagreements(instance, every):
        raise AssertionError(f"{instance.name}: " + "; ".join(said))
    proposals, short = batch.chain(problem, instance.length, instance.distance)
    steps = [
        {"films": sorted(each), "best": best_far_from(every, proposals[:place], instance.distance), "triple": list(value(each, problem).triple)}
        for place, each in enumerate(proposals)
    ]
    return {"instance": instance.encoded(), "steps": steps, "exhausted": short}


def generate():
    CASES.parent.mkdir(parents=True, exist_ok=True)
    written = [solved(each) for each in cases()]
    CASES.write_text(json.dumps(written, indent=1) + "\n")
    print(f"wrote {len(written)} cases to {CASES}")


if __name__ == "__main__":
    generate()
