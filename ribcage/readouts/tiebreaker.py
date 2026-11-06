"""The tiebreaker rules' keys: a slate's exact value under each, comparable and higher being better, pure over plain data (#175).

A rule is a name here and its levels in `ribcage.solver.model.LEVELS`; a test holds the two to the same names.
Floor and Σrep come before any rule and are not configurable (#10).
"""

from ribcage.readouts.slate import film_points


def total(films, records):
    """A slate's total: everyone's score for every film in it, a veto -2 and an unplaced film 0, which is the sum of its film points (#6, #24).

    `records` are (voter, film, score, vetoed, seen_it).
    """
    on_slate = set(films)
    return sum(film_points([(score, vetoed)]) for _, film, score, vetoed, _ in records if film in on_slate)


KEYS = {"total": total}
DEFAULT = "total"
