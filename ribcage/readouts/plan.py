"""The set readouts of a slate, over plain data: the same for a hand-built and a solved slate (#10, #12, #24, #147)."""

from dataclasses import dataclass

from ribcage.readouts.slate import film_points, slate_sum


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


@dataclass(frozen=True)
class FilmLine:
    """One slate film: its runtime, its film points over every voter, whom it represents and how many scored it positively."""

    film: object
    runtime: int
    points: int
    represents: tuple  # (voter, pins) in voter order
    likes: int
    most: bool  # carries the most film points


@dataclass(frozen=True)
class Person:
    """One voter's row of the breakdown: the representative, the slate sum and, at zero, the best eligible candidate as (film, score)."""

    voter: object
    representative: object
    representation: int
    out: str
    pins: bool
    slate_sum: int
    best_eligible: object  # (film, score) or None
    served: str  # "best", "worst" or "": the floor set's best- and worst-served slate sums


@dataclass(frozen=True)
class Breakdown:
    films: tuple
    people: tuple


def breakdown(read, slate, runtimes, held, candidates, candidate_records):
    """The slate's film points and slate sums beside `read`, a `Plan` of the same `slate` (film keys in slate order) (#24, #148).

    `held` are the (voter, film, score, vetoed, seen_it) records on the slate's films, `candidates` the ballot's film keys in slate order
    with their `candidate_records`; a dropped film is on the slate but not a candidate, so it is never offered to a voter at zero.
    """
    on_slate = set(slate)
    by_film, by_voter, likes = {}, {}, {}
    for voter, film, score, vetoed, _ in held:
        if film not in on_slate:
            continue
        by_film.setdefault(film, []).append((score, vetoed))
        by_voter.setdefault(voter, []).append((score, vetoed))
        if not vetoed and score is not None and score > 0:
            likes[film] = likes.get(film, 0) + 1
    points = {film: film_points(by_film.get(film, ())) for film in slate}
    top = max(points.values(), default=0)
    represented = {}
    for each in read.rows:
        if each.representative is not None:
            represented.setdefault(each.representative, []).append((each.voter, each.pins))
    films = tuple(FilmLine(film, runtimes[film], points[film], tuple(represented.get(film, ())), likes.get(film, 0), points[film] == top) for film in slate)
    eligible = {}
    for voter, film, score, vetoed, seen_it in candidate_records:
        eligible.setdefault(voter, []).append((film, score, vetoed, seen_it))
    sums = {each.voter: slate_sum(by_voter.get(each.voter, ())) for each in read.rows}
    members = [sums[each.voter] for each in read.rows if not each.out]
    best, worst = max(members, default=0), min(members, default=0)
    people = tuple(
        Person(
            each.voter,
            each.representative,
            each.representation,
            each.out,
            each.pins,
            sums[each.voter],
            _best_eligible(candidates, eligible.get(each.voter, ())) if not each.out and each.representation == 0 else None,
            "" if each.out or best == worst else "best" if sums[each.voter] == best else "worst" if sums[each.voter] == worst else "",
        )
        for each in read.rows
    )
    return Breakdown(films, people)


def _best_eligible(candidates, rows):
    """The voter's best-scored candidate they have neither seen nor vetoed, with a positive score, as (film, score), or None (#17, #148)."""
    film, score = representative(candidates, rows)
    return None if film is None else (film, score)
