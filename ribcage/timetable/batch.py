"""The batch as SOLVE finds it on Compare: the slates and the banner's facts, resumed from the admin's session while the problem is the same, never stored in the database (#17, #165, #166)."""

from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from django.conf import settings

from ribcage.readouts.basis import Basis
from ribcage.solver.model import SCALES, solve
from ribcage.solver.objective import Problem

NOTHING_FITS = "Nothing fits the budget, so the proposal is the empty slate."
NO_FLOOR = "Nobody is in the floor set, so the tiebreaker ({rule}) alone is optimised."
NO_FILMS = "No film is approved, so there is nothing to propose."
ALL_OUT = "Every film is fixed out, so there is nothing to propose."


def solver_sources():
    """The files whose bytes a solve's result depends on: the solver, the film points and floor set it calls and this chain (#166)."""
    here = Path(__file__).resolve()
    ribcage = here.parent.parent
    return [*sorted((ribcage / "solver").glob("*.py")), ribcage / "readouts" / "floor.py", ribcage / "readouts" / "slate.py", ribcage / "readouts" / "tiebreaker.py", here]


def code_digest():
    """A digest of the code and library a solve runs on, so a release that changes any of it ends every kept chain without anyone bumping a number (#166)."""
    digest = sha256(version("highspy").encode())
    for each in solver_sources():
        digest.update(each.read_bytes())
    return digest.hexdigest()


SOLVER_CODE = code_digest()


@dataclass(frozen=True)
class Batch:
    slates: tuple  # frozensets of film keys, the best first
    solved_ms: int
    ending: str  # the banner's message in the objective's terms, or ""
    stopped: str = ""  # why "more" is unavailable, or "" while the chain may go on (#166)
    rounds: int = 1  # how far "more" stands, which a changed problem sets back to one
    kept: dict = None  # what the admin's session holds for the next render: the problem's digest, the slates and whether the chain ended
    solving: bool = True  # whether this render solved anything, so `solved_ms` is only that time


def problem_of(on, multiplier, basis=Basis(), tiebreaker=None):
    """SOLVE's `Problem` from the stored votes: the ballot's films but those fixed out, every voter counted until #167's knobs set one aside, the films fixed in pinned (#168), under the tiebreaker `SLATE_TIEBREAKER` names unless one is given (#175)."""
    runtimes = {film: on.runtimes[film] for film in on.candidates if film not in basis.fixed_out}
    records = tuple(each for each in on.records if each[1] in runtimes)
    pinned = tuple(film for film in on.candidates if film in runtimes and film in basis.fixed_in)
    return Problem(on.voters, runtimes, records, on.budget, on.floor_set, multiplier, pinned, settings.SLATE_TIEBREAKER if tiebreaker is None else tiebreaker)


def pins_say(given, titles):
    """The ending for pins that alone exceed the budget, naming each with its runtime; nothing is dropped (#17, #24, #168)."""
    named = ", ".join(f"{titles[film]} ({given.runtimes[film]}m)" for film in given.fixed_in)
    return f"The films fixed in alone exceed the budget: {named}. Nothing dropped."


def ending_of(given, slates=(), titles=None, basis=Basis()):
    """The ending the problem has, if any: pins the solver found infeasible, no films, nothing fitting or no floor; nothing is said for everything fitting or no budget (#17, #165, #168).

    Nothing pre-checks the pins: it is the first solve's status, no slate at all, that reports them.
    """
    if given.fixed_in and not slates:
        return pins_say(given, titles or {film: film for film in given.fixed_in})
    if not given.runtimes:
        return ALL_OUT if basis.fixed_out else NO_FILMS
    if given.budget is not None and min(given.runtimes.values()) > given.budget:
        return NOTHING_FITS
    return NO_FLOOR.format(rule=given.tiebreaker) if not given.floor_set.size else ""


def stopped_says(distance, slates=(True,)):
    if not slates:
        return "No slate holds the films fixed in."
    return f"No other slate differs from these by {distance} or more films."


def chain(given, length, distance, kept=(), ended=False):
    """Up to `length` slates, each at least `distance` films from every one before, and whether the cut stopped it short (#17, #166).

    The first is the optimum; the chain is deterministic, so a longer ask only extends a shorter one.
    `kept` are slates an earlier call found for this same `given`, which it resumes from; `ended` says that call was stopped short, so nothing is solved again.
    """
    found = [frozenset(each) for each in kept][:length]
    if ended and len(found) < length:
        return found, True
    scale = SCALES[given.tiebreaker](given)
    while len(found) < length:
        best = solve(given, found=found, distance=distance, scale=scale)
        # The empty pool has one slate only; solving it again would repeat it, never pad (#17).
        if best is None or best in found:
            return found, True
        found.append(best)
    return found, False


def fingerprint(given, size, distance):
    """Everything a solve reads, as one digest: the same digest means the kept slates are what a full re-solve would find (#166)."""
    reads = (
        given.voters,
        sorted(given.runtimes.items()),
        sorted(given.records, key=repr),
        given.budget,
        given.floor_set.members,
        given.floor_set.out,
        given.multiplier,
        given.fixed_in,
        given.tiebreaker,
        size,
        distance,
        SOLVER_CODE,
    )
    return sha256(repr(reads).encode()).hexdigest()


def propose(on, multiplier, rounds=1, kept=None, basis=Basis(), titles=None):
    """The batch over `on`, a `ledger.StoredVotes`: `rounds` times `BATCH_SIZE` proposals at most, the admin's "more" being the count (#166).

    `kept` is what the last call returned as `Batch.kept`. When it answers to the same problem, only the proposals still missing are solved;
    when the problem has changed, it is dropped and the batch starts again at one round, as a new budget does (#17).
    """
    given = problem_of(on, multiplier, basis)
    size, distance = settings.BATCH_SIZE, settings.DIVERSITY_CUT
    mark = fingerprint(given, size, distance)
    same = kept is not None and kept["print"] == mark
    if kept is not None and not same:
        rounds = 1
    before = kept["slates"] if same else ()
    ended = same and kept["short"]
    length = rounds * size
    solving = not (ended or len(before) >= length)
    started = perf_counter()
    slates, short = chain(given, length, distance, before, ended)
    memory = {"print": mark, "slates": [sorted(each) for each in slates], "short": short}
    return Batch(tuple(slates), round((perf_counter() - started) * 1000), ending_of(given, slates, titles, basis), stopped_says(distance, slates) if short else "", rounds, memory, solving)
