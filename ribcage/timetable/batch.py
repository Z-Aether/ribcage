"""The batch as SOLVE finds it on Compare: the slates and the banner's facts, resumed from the admin's session while the problem is the same, never stored in the database (#17, #165, #166)."""

from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from django.conf import settings

from ribcage.solver.model import solve
from ribcage.solver.objective import Problem, scale_of

NOTHING_FITS = "Nothing fits the budget, so the proposal is the empty slate."
NO_FLOOR = "Nobody is in the floor set, so the total alone is optimised."
NO_FILMS = "No film is approved, so there is nothing to propose."


def solver_sources():
    """The files whose bytes a solve's result depends on: the solver, the film points it calls and this chain (#166)."""
    here = Path(__file__).resolve()
    ribcage = here.parent.parent
    return [*sorted((ribcage / "solver").glob("*.py")), ribcage / "readouts" / "slate.py", here]


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


def problem_of(on, multiplier):
    """SOLVE's `Problem` from the stored votes: the ballot's films, every voter counted until #167's knobs set one aside."""
    runtimes = {film: on.runtimes[film] for film in on.candidates}
    records = tuple(each for each in on.records if each[1] in runtimes)
    return Problem(on.voters, runtimes, records, on.budget, on.floor_set, multiplier)


def ending_of(given):
    """The ending that needs no knob, if the problem has one: nothing is said for everything fitting or no budget (#17, #165)."""
    if not given.runtimes:
        return NO_FILMS
    if given.budget is not None and min(given.runtimes.values()) > given.budget:
        return NOTHING_FITS
    return NO_FLOOR if not given.floor_set.size else ""


def stopped_says(distance):
    return f"No other slate differs from these by {distance} or more films."


def chain(given, length, distance, kept=(), ended=False):
    """Up to `length` slates, each at least `distance` films from every one before, and whether the cut stopped it short (#17, #166).

    The first is the optimum; the chain is deterministic, so a longer ask only extends a shorter one.
    `kept` are slates an earlier call found for this same `given`, which it resumes from; `ended` says that call was stopped short, so nothing is solved again.
    """
    found = [frozenset(each) for each in kept][:length]
    if ended and len(found) < length:
        return found, True
    scale = scale_of(given)
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
        size,
        distance,
        SOLVER_CODE,
    )
    return sha256(repr(reads).encode()).hexdigest()


def propose(on, multiplier, rounds=1, kept=None):
    """The batch over `on`, a `ledger.StoredVotes`: `rounds` times `BATCH_SIZE` proposals at most, the admin's "more" being the count (#166).

    `kept` is what the last call returned as `Batch.kept`. When it answers to the same problem, only the proposals still missing are solved;
    when the problem has changed, it is dropped and the batch starts again at one round, as a new budget does (#17).
    """
    given = problem_of(on, multiplier)
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
    return Batch(tuple(slates), round((perf_counter() - started) * 1000), ending_of(given), stopped_says(distance) if short else "", rounds, memory, solving)
