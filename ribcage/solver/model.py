"""SOLVE's MILP in HiGHS: the best slate under the budget, pure over a `Problem` (#6, #10, #33, #165). Ported from tools/slate-solver-bench/mip.js."""

import highspy
import numpy

from ribcage.readouts.slate import film_points
from ribcage.solver.objective import scale_of


def solve(problem, found=(), distance=2, scale=None):
    """The best slate as a frozenset of films, or None where none exists, as when the films fixed in alone exceed the budget (#168).

    `found` are slates already proposed; each is cut off by a Hamming distance of at least `distance`, the seam for #166's diversity cut and "more".
    `scale` is K, computed per solve unless a test forces another.
    """
    films = sorted(problem.runtimes)
    if not films:
        return frozenset()
    k = scale_of(problem) if scale is None else scale
    by_voter, points = {}, {film: [] for film in films}
    for voter, film, score, vetoed, seen_it in problem.on_the_ballot():
        points[film].append((score, vetoed))
        by_voter.setdefault(voter, {})[film] = (score, vetoed, seen_it)

    highs = highspy.Highs()
    highs.setOptionValue("output_flag", False)
    # The default gap tolerates enough slack to lose the total's tie-break and still report Optimal (#6).
    highs.setOptionValue("mip_rel_gap", 0.0)
    highs.setOptionValue("mip_abs_gap", 0.0)
    highs.changeObjectiveSense(highspy.ObjSense.kMaximize)

    columns = 0

    def column(cost, upper, lower=0):
        nonlocal columns
        highs.addCol(float(cost), float(lower), float(upper), 0, numpy.array([], dtype=numpy.int32), numpy.array([], dtype=numpy.float64))
        highs.changeColIntegrality(columns, highspy.HighsVarType.kInteger)
        columns += 1
        return columns - 1

    def row(upper, terms, lower=-highspy.kHighsInf):
        ordered = sorted(terms.items())
        highs.addRow(float(lower), float(upper), len(ordered), numpy.array([c for c, _ in ordered], dtype=numpy.int32), numpy.array([v for _, v in ordered], dtype=numpy.float64))

    pinned = set(problem.fixed_in)
    x = {film: column(film_points(points[film]), 1, 1 if film in pinned else 0) for film in films}
    if problem.budget is not None:
        row(problem.budget, {x[film]: problem.runtimes[film] for film in films})
    members = problem.floor_set.members
    # Only a positive score, unvetoed and unseen, can represent its voter; the rest is worth nothing (#10).
    may = {
        voter: {film: score for film, (score, vetoed, seen_it) in by_voter.get(voter, {}).items() if score is not None and score > 0 and not vetoed and not seen_it}
        for voter in members
    }
    floor = column(k * problem.weight, max((score for each in may.values() for score in each.values()), default=0)) if members else None
    for voter in members:
        mine = {film: (column(k * score, 1), score) for film, score in may[voter].items()}
        for film, (y, _) in mine.items():
            row(0, {y: 1, x[film]: -1})
        if mine:
            row(1, {y: 1 for y, _ in mine.values()})
        row(0, {floor: 1, **{y: -score for y, score in mine.values()}})
    for slate in found:
        inside = set(slate)
        # Σ over films outside minus Σ over films inside ≥ distance − |S|: at least `distance` films differ.
        row(highspy.kHighsInf, {x[film]: (-1 if film in inside else 1) for film in films}, lower=distance - len(inside & set(films)))

    highs.run()
    status = highs.getModelStatus()
    if status in (highspy.HighsModelStatus.kInfeasible, highspy.HighsModelStatus.kUnboundedOrInfeasible):
        return None
    if status != highspy.HighsModelStatus.kOptimal:
        raise RuntimeError(f"SOLVE ended {highs.modelStatusToString(status)}")
    values = highs.getSolution().col_value
    return frozenset(film for film in films if round(values[x[film]]) == 1)
