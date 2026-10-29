"""The set readouts of a slate, over plain data: the same for a hand-built and a solved slate (#10, #12, #24, #147)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    """One voter: in the floor set, their representative and its representation; out, the reason instead."""

    voter: object
    representative: object  # a film key, or None
    representation: int
    out: str  # the reason, or "" for a voter in the floor set
    pins: bool  # in the floor set at the floor


@dataclass(frozen=True)
class Vetoed:
    film: object
    vetoers: tuple


@dataclass(frozen=True)
class Plan:
    films: int
    screen_time: int
    budget: int  # or None
    rows: tuple
    floor: int  # or None with an empty floor set
    sigma_rep: int
    vetoed: tuple

    @property
    def over(self):
        return self.budget is not None and self.screen_time > self.budget


def representative(slate, rows):
    """A voter's best-scored slate film they have neither vetoed nor seen, as (film, score), or (None, 0); a tie keeps the earlier film (#10).

    `rows` are the voter's (film, score, vetoed, seen_it) records; a film in the slate has no more than one.
    """
    best, score = None, 0
    held = {film: (points, vetoed, seen_it) for film, points, vetoed, seen_it in rows}
    for film in slate:
        points, vetoed, seen_it = held.get(film, (None, False, False))
        if points is not None and points > score and not vetoed and not seen_it:
            best, score = film, points
    return best, score


def plan(voters, slate, runtimes, records, floor_set, budget):
    """The set readouts of `slate` (film keys, in the order wanted) with its `runtimes` by film.

    `voters` are in the order wanted, `records` are (voter, film, score, vetoed, seen_it) and `floor_set` a `readouts.floor.FloorSet`.
    The slate is whatever is on the timetable, a dropped film included, and a record on a film outside it counts for nothing (#147, #26 §5).
    """
    on_slate = set(slate)
    by_voter, vetoers = {}, {}
    for voter, film, score, vetoed, seen_it in records:
        if film not in on_slate:
            continue
        by_voter.setdefault(voter, []).append((film, score, vetoed, seen_it))
        if vetoed:
            vetoers.setdefault(film, set()).add(voter)
    chosen = {each: representative(slate, by_voter.get(each, ())) for each in floor_set.members}
    floor = min((score for _, score in chosen.values()), default=None)
    reasons = dict(floor_set.out)
    rows = tuple(
        Row(each, *chosen[each], "", chosen[each][1] == floor) if each in chosen else Row(each, None, 0, reasons[each], False)
        for each in voters
        if each in chosen or each in reasons
    )
    vetoed = tuple(Vetoed(film, tuple(each for each in voters if each in vetoers[film])) for film in slate if film in vetoers)
    return Plan(len(slate), sum(runtimes[film] for film in slate), budget, rows, floor, sum(score for _, score in chosen.values()), vetoed)


def clock(minutes):
    """Screen time as 7h06m, 9h or 40m."""
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return f"{minutes}m"
    return f"{hours}h{minutes:02d}m" if minutes else f"{hours}h"
