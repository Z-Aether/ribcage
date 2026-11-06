"""SOLVE's MILP in HiGHS: the best slate under the budget, pure over a `Problem` (#6, #10, #33, #165). Ported from tools/slate-solver-bench/mip.js."""

import highspy
import numpy

from ribcage.readouts.slate import film_points
from ribcage.solver.objective import scale_of


class Model:
    """The MILP a rule's levels optimise: the HiGHS instance, the film columns and what a level needs to set its objective (#175, #176).

    `base` is the floor and representation columns with the cost each carries in the objective's first part, `W·m + Σrep` scaled by K.
    `points` are the films' (score, vetoed) records and `sums` the counted voters' points by film, voter by voter.
    """

    def __init__(self, highs, films, x, points, k, base, sums):
        self.highs, self.films, self.x, self.points, self.k, self.base, self.sums = highs, films, x, points, k, base, sums
        self.columns = 0

    def column(self, cost, upper, lower=0, integer=True):
        self.highs.addCol(float(cost), float(lower), float(upper), 0, numpy.array([], dtype=numpy.int32), numpy.array([], dtype=numpy.float64))
        if integer:
            self.highs.changeColIntegrality(self.columns, highspy.HighsVarType.kInteger)
        self.columns += 1
        return self.columns - 1

    def row(self, upper, terms, lower=-highspy.kHighsInf):
        ordered = sorted(terms.items())
        self.highs.addRow(float(lower), float(upper), len(ordered), numpy.array([c for c, _ in ordered], dtype=numpy.int32), numpy.array([v for _, v in ordered], dtype=numpy.float64))

    @property
    def optimal(self):
        return self.highs.getModelStatus() == highspy.HighsModelStatus.kOptimal

    def objective(self):
        """The finished level's objective, whole: every level's coefficients are whole numbers over whole columns."""
        return round(self.highs.getInfo().objective_function_value)


def total_levels(model):
    """The rule `total`: one solve, `K·(W·m + Σrep) + T`, the floor and representation columns already costing the K-scaled part (#33, #165)."""
    for film in model.films:
        model.highs.changeColCost(model.x[film], float(film_points(model.points[film])))
    model.highs.run()


def leximin_level(model, count):
    """The columns level `count` prices, as (column, cost) pairs, adding the rows that define them; level 0 is the floor and Σrep columns already there.

    Level k > 0 maximises `L_k = k·t − Σ d_i` with `d_i ≥ t − s_i` for each counted voter, `d_i ≥ 0` and t free.
    """
    if not count:
        return model.base
    voters = list(model.sums)
    bar = model.column(count, highspy.kHighsInf, -highspy.kHighsInf, integer=False)
    short = [model.column(-1, highspy.kHighsInf, integer=False) for _ in voters]
    for voter, shortfall in zip(voters, short):
        # d ≥ t − s  ⇔  d − t + Σ points·x ≥ 0
        model.row(highspy.kHighsInf, {shortfall: 1, bar: -1, **{model.x[film]: points for film, points in model.sums[voter].items() if points}}, lower=0)
    return [(bar, count), *[(column, -1) for column in short]]


def leximin_levels(model):
    """The rule `leximin`, level by level (#176).

    Level 0 is `W·m + Σrep`, which K does not scale here; then for k = 1 to n, `L_k`, the sum of the k smallest slate sums, maximised in that order (cumulative ordered sums).
    Each finished level is held at its optimum as a row before the next starts, so the levels are lexicographic without weights that would grow past double precision.
    Slate sums, hence every optimum, are whole, so a held level is exact. A level that ends other than optimal, as an infeasible level 0 does for pins over the budget, ends the solve there (#168).
    HiGHS's own lexicographic objectives (`addLinearObjective` with priorities, highspy 1.15.1) were tried first and left out: on this MIP they answered a slate worse than enumeration's on 69 of 72 seeded draws, so the loop is by hand and the oracle agrees on all of them.
    """
    highs = model.highs
    for count in range(len(model.sums) + 1):
        priced = leximin_level(model, count)
        highs.run()
        # The last level's solution is the answer, so holding it would only unset the model's status.
        if not model.optimal or count == len(model.sums):
            return
        model.row(highspy.kHighsInf, dict(priced), lower=model.objective())
        for column, _ in priced:
            highs.changeColCost(column, 0.0)


# A rule's levels, by the same names as `readouts.tiebreaker.KEYS`; each gets the whole model and leaves the optimal solution in it (#175).
LEVELS = {"total": total_levels, "leximin": leximin_levels}
# K for a rule, by the same names: `total` folds T under the floor and Σrep and needs K to keep it there, `leximin` folds nothing in (#33, #176).
SCALES = {"total": scale_of, "leximin": lambda problem: 1}


def solve(problem, found=(), distance=2, scale=None):
    """The best slate as a frozenset of films, or None where none exists, as when the films fixed in alone exceed the budget (#168).

    `found` are slates already proposed; each is cut off by a Hamming distance of at least `distance`, the seam for #166's diversity cut and "more".
    `scale` is K, computed per solve by the rule unless a test forces another.
    """
    films = sorted(problem.runtimes)
    if not films:
        return frozenset()
    k = SCALES[problem.tiebreaker](problem) if scale is None else scale
    by_voter, points = {}, {film: [] for film in films}
    for voter, film, score, vetoed, seen_it in problem.on_the_ballot():
        points[film].append((score, vetoed))
        by_voter.setdefault(voter, {})[film] = (score, vetoed, seen_it)
    # The counted voters' points by film, from the readouts' own `film_points` so a veto and a disregarded veto count as the breakdown counts them (#148, #167, #176).
    sums = {voter: {film: film_points([(score, vetoed)]) for film, (score, vetoed, _) in by_voter.get(voter, {}).items()} for voter in problem.floor_set.counted}

    highs = highspy.Highs()
    highs.setOptionValue("output_flag", False)
    # The default gap tolerates enough slack to lose the tiebreaker and still report Optimal (#6); a level held at its optimum needs it at every level (#176).
    highs.setOptionValue("mip_rel_gap", 0.0)
    highs.setOptionValue("mip_abs_gap", 0.0)
    highs.changeObjectiveSense(highspy.ObjSense.kMaximize)

    model = Model(highs, films, {}, points, k, [], sums)
    pinned = set(problem.fixed_in)
    x = model.x = {film: model.column(0, 1, 1 if film in pinned else 0) for film in films}
    if problem.budget is not None:
        model.row(problem.budget, {x[film]: problem.runtimes[film] for film in films})
    members = problem.floor_set.members
    # Only a positive score, unvetoed and unseen, can represent its voter; the rest is worth nothing (#10).
    may = {
        voter: {film: score for film, (score, vetoed, seen_it) in by_voter.get(voter, {}).items() if score is not None and score > 0 and not vetoed and not seen_it}
        for voter in members
    }

    def costing(cost, upper):
        column = model.column(cost, upper)
        model.base.append((column, cost))
        return column

    floor = costing(k * problem.weight, max((score for each in may.values() for score in each.values()), default=0)) if members else None
    for voter in members:
        mine = {film: (costing(k * score, 1), score) for film, score in may[voter].items()}
        for film, (y, _) in mine.items():
            model.row(0, {y: 1, x[film]: -1})
        if mine:
            model.row(1, {y: 1 for y, _ in mine.values()})
        model.row(0, {floor: 1, **{y: -score for y, score in mine.values()}})
    for slate in found:
        inside = set(slate)
        # Σ over films outside minus Σ over films inside ≥ distance − |S|: at least `distance` films differ.
        model.row(highspy.kHighsInf, {x[film]: (-1 if film in inside else 1) for film in films}, lower=distance - len(inside & set(films)))

    LEVELS[problem.tiebreaker](model)
    status = highs.getModelStatus()
    if status in (highspy.HighsModelStatus.kInfeasible, highspy.HighsModelStatus.kUnboundedOrInfeasible):
        return None
    if status != highspy.HighsModelStatus.kOptimal:
        raise RuntimeError(f"SOLVE ended {highs.modelStatusToString(status)}")
    values = highs.getSolution().col_value
    return frozenset(film for film in films if round(values[x[film]]) == 1)
