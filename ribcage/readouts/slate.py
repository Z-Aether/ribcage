"""Film points and slate order: plain functions over plain data, which Compare's readouts and the shortlist extend (#24, #36, #137)."""

from dataclasses import dataclass

# A veto counts this in a film's points, though it is never stored as a score (#24).
VETO_POINTS = -2


@dataclass(frozen=True)
class SlateEntry:
    """One film as the slate orders it: how many vetoed it, its film points and its title; `key` is whatever the caller wants back."""

    key: object
    title: str
    vetoes: int
    points: int


def film_points(records):
    """The sum of everyone's score for a film from their (score, vetoed) records: a veto counts -2, an unplaced film 0 (#24)."""
    return sum(VETO_POINTS if vetoed else score or 0 for score, vetoed in records)


def slate_order(standings):
    """Fewest vetoes first, then most film points, then title (#36)."""
    return sorted(standings, key=lambda each: (each.vetoes, -each.points, each.title.casefold(), each.title))
