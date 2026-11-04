"""SOLVE's problem and its objective's exact value for any film set, pure over plain data: the model, the tests and the oracle check against it (#6, #33, #165)."""

from dataclasses import dataclass

from ribcage.readouts import ledger, plan
from ribcage.readouts.floor import FloorSet
from ribcage.readouts.slate import DISREGARDED


@dataclass(frozen=True)
class Problem:
    """What SOLVE reads: the voters the total counts, the candidates' runtimes by film, the budget (or None) and the floor set.

    `records` are (voter, film, score, vetoed, seen_it) of those voters alone, so a voter a knob sets aside is dropped here before the solve (#167).
    A record on a film outside `runtimes` is a dropped film's and counts for nobody (#26 §5).
    """

    voters: tuple
    runtimes: dict
    records: tuple
    budget: int  # or None
    floor_set: FloorSet
    multiplier: int  # FLOOR_WEIGHT_MULTIPLIER
    fixed_in: tuple = ()  # candidate films the slate must hold, in slate order; a film fixed out is not in `runtimes` at all (#168)

    @property
    def weight(self):
        """W = c·|floor set|, so 0 with an empty floor set, which leaves the total alone (#33)."""
        return self.multiplier * self.floor_set.size

    def on_the_ballot(self):
        return [each for each in self.records if each[1] in self.runtimes]


def scale_of(problem):
    """K = 2·B + 1, B being every counted voter's |score| summed over the candidates, a veto counting 2 and a disregarded one 0, so K always exceeds 2·max|T| (#33, #165)."""
    bound = sum(0 if vetoed == DISREGARDED else 2 if vetoed else abs(score or 0) for _, _, score, vetoed, _ in problem.on_the_ballot())
    return 2 * bound + 1


@dataclass(frozen=True)
class Value:
    floor: int  # or None with an empty floor set
    sigma_rep: int
    total: int
    weight: int
    scale: int

    @property
    def integer(self):
        """K·(W·m + Σrep) + T, what the solver maximises."""
        return self.scale * ((self.floor or 0) * self.weight + self.sigma_rep) + self.total

    @property
    def triple(self):
        return self.floor, self.sigma_rep, self.total


def value(films, problem, scale=None):
    """The objective of the film set `films` (keys of candidates), from the same readouts the ledger draws, never from the solver's float (#6)."""
    slate = sorted(set(films))
    on_slate = set(slate)
    held = [each for each in problem.on_the_ballot() if each[1] in on_slate]
    read = plan.plan(problem.voters, slate, {film: problem.runtimes[film] for film in slate}, held, problem.floor_set, problem.budget)
    return Value(read.floor, read.sigma_rep, ledger.total(slate, held), problem.weight, scale_of(problem) if scale is None else scale)
