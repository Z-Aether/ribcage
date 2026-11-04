"""The batch as SOLVE finds it on Compare's every render: the slates and the banner's facts, never stored (#17, #165). #166 adds the rest of the batch here."""

from dataclasses import dataclass
from time import perf_counter

from ribcage.solver.model import solve
from ribcage.solver.objective import Problem

NOTHING_FITS = "Nothing fits the budget, so the proposal is the empty slate."
NO_FLOOR = "Nobody is in the floor set, so the total alone is optimised."
NO_FILMS = "No film is approved, so there is nothing to propose."


@dataclass(frozen=True)
class Batch:
    slates: tuple  # frozensets of film keys, the best first
    solved_ms: int
    ending: str  # the banner's message in the objective's terms, or ""


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


def propose(on, multiplier):
    """The batch over `on`, a `ledger.StoredVotes`, timed."""
    given = problem_of(on, multiplier)
    started = perf_counter()
    best = solve(given)
    return Batch(() if best is None else (best,), round((perf_counter() - started) * 1000), ending_of(given))
