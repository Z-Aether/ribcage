"""The tiebreaker rules' keys: a slate's exact value under each, comparable and higher being better, pure over plain data (#175, #176).

A rule is a name here and its levels in `ribcage.solver.model.LEVELS`; a test holds the two to the same names.
Floor and Σrep come before any rule and are not configurable (#10).
A key is `key(films, records, floor_set)`: `records` are (voter, film, score, vetoed, seen_it) and `floor_set` says whom a rule counts.
"""

from dataclasses import dataclass

from ribcage.readouts.slate import film_points, slate_sum


def total(films, records, floor_set=None):
    """A slate's total: everyone's score for every film in it, a veto -2 and an unplaced film 0, which is the sum of its film points (#6, #24).

    `floor_set` is unused: the total counts every record it is given.
    """
    on_slate = set(films)
    return sum(film_points([(score, vetoed)]) for _, film, score, vetoed, _ in records if film in on_slate)


def slate_sums(films, records, floor_set):
    """Each counted voter's slate sum on `films`, by voter, exactly as `plan.breakdown` reads it: a veto -2, a disregarded one 0, an unsorted film 0 (#148, #167, #176).

    A record on a film outside `films` counts for nobody, and so does a voter `floor_set.counted` leaves out.
    """
    on_slate = set(films)
    held = {voter: [] for voter in floor_set.counted}
    for voter, film, score, vetoed, _ in records:
        if film in on_slate and voter in held:
            held[voter].append((score, vetoed))
    return {voter: slate_sum(each) for voter, each in held.items()}


def leximin(films, records, floor_set):
    """The slate sums of the counted voters sorted lowest first, compared as tuples: the highest lowest sum wins, a tie going to the second-lowest and so on (#176)."""
    return tuple(sorted(slate_sums(films, records, floor_set).values()))


def lowest(sums):
    """The voters holding the lowest slate sum in `sums` (by voter), in their order; none where `sums` is empty."""
    floor = min(sums.values(), default=None)
    return tuple(voter for voter, each in sums.items() if each == floor)


@dataclass(frozen=True)
class Gap:
    """Where a leximin key falls short of another: the place counted from the lowest slate sum, 1 for the lowest, and by how much there."""

    position: int
    by: int


def leximin_distance(key, best):
    """The first place, from the lowest slate sum, where `key` differs from `best`'s and by how much (`key` minus `best`), or None where they are the same (#176).

    Both are keys over the same counted voters, so they have the same length.
    """
    for place, (mine, theirs) in enumerate(zip(key, best), 1):
        if mine != theirs:
            return Gap(place, mine - theirs)
    return None


KEYS = {"total": total, "leximin": leximin}
DEFAULT = "leximin"
