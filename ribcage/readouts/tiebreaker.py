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


def signed(distance):
    """A distance from the best row: = when level, else the figure with its sign (a true minus sign) (#164)."""
    return "=" if not distance else f"{distance:+d}".replace("-", "−")


def ordinal(place):
    """1st, 2nd, 3rd, 4th, 11th, 21st."""
    teens = place % 100 in (11, 12, 13)
    return f"{place}{'th' if teens else {1: 'st', 2: 'nd', 3: 'rd'}.get(place % 10, 'th')}"


def leximin_words(key, best):
    """Where `key` falls short of or beats `best`, as the ledger says it: *−1 at 2nd*, or *=* when the two are the same throughout (#177)."""
    gap = leximin_distance(key, best)
    return "=" if gap is None else f"{signed(gap.by)} at {ordinal(gap.position)}"


def _sums(key):
    return " · ".join(str(each) for each in key)


@dataclass(frozen=True)
class Column:
    """What a rule shows on Compare, in words over its key: its column's header, the figure and the distance from the best row's key, its line in the breakdown and its row in the swap (#177).

    `swap` is the swap's row for the rule, or None where the ledger's *Total* row already says it; `marks_lowest` is whether the strip marks the voters holding the lowest slate sum.
    A rule's readouts live here and the templates only draw them.
    """

    header: str
    value: object  # key -> str
    distance: object  # (key, best key) -> str
    line: object  # key -> str, "" for none
    swap: object  # key -> str, or None for no row
    marks_lowest: bool


COLUMNS = {
    "total": Column("Total", str, lambda key, best: signed(key - best), lambda key: "", None, False),
    "leximin": Column("Leximin", lambda key: str(key[0]) if key else "–", leximin_words, lambda key: f"leximin {_sums(key)}" if key else "", _sums, True),
}

KEYS = {"total": total, "leximin": leximin}
DEFAULT = "leximin"
