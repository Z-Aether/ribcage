"""The slate ledger's readouts over plain data: a row's reads, standing and tier across rows, the film dots (#24, #164).

Every read of a row is a function of its film set and the `StoredVotes`. The `StoredVotes` hold the votes as the basis counts them; the slate order is the stored votes' alone, whatever the basis (#17, #36, #167).
"""

from dataclasses import dataclass

from ribcage.readouts import plan as plans
from ribcage.readouts.basis import Basis, under
from ribcage.readouts.floor import FloorSet
from ribcage.readouts.slate import SlateEntry, film_points, slate_order


@dataclass(frozen=True)
class StoredVotes:
    """What every row is read against: the voters, the floor set, the records under the basis, the budget and the films' runtimes and slate order."""

    voters: tuple  # ids in the order wanted
    floor_set: FloorSet
    records: tuple  # (voter, film, score, vetoed, seen_it) on every film a row can hold, the ballot's included
    runtimes: dict  # by film, for every film a row can hold
    rank: dict  # by film: its place in slate order over everyone's records
    candidates: tuple  # the ballot's films in slate order
    budget: int  # or None


def stored_votes(voters, floor_set, records, titles, runtimes, candidates, budget, basis=Basis()):
    """The votes over `titles` (every film a row can hold, by key), ranked in slate order by the stored records, then counted under `basis` (#36, #167).

    `floor_set` is the one the basis gives (`set_aside` of `readouts.floor.floor_set`).
    """
    by_film = {}
    for _, film, score, vetoed, _ in records:
        if film in titles:
            by_film.setdefault(film, []).append((score, vetoed))
    ranked = slate_order(
        [SlateEntry(film, title, sum(1 for _, vetoed in by_film.get(film, ()) if vetoed), film_points(by_film.get(film, ()))) for film, title in titles.items()]
    )
    rank = {each.key: place for place, each in enumerate(ranked)}
    on_the_ballot = set(candidates)
    return StoredVotes(tuple(voters), floor_set, under(records, basis), dict(runtimes), rank, tuple(each.key for each in ranked if each.key in on_the_ballot), budget)


@dataclass(frozen=True)
class Read:
    """One row's readouts: its films in slate order, the set readouts, the breakdown and the total."""

    films: tuple
    plan: object
    breakdown: object
    total: int


def total(films, records):
    """A slate's total: everyone's score for every film in it, a veto -2 and an unplaced film 0, which is the sum of its film points (#6, #24).

    `records` are (voter, film, score, vetoed, seen_it).
    """
    on_slate = set(films)
    return sum(film_points([(score, vetoed)]) for _, film, score, vetoed, _ in records if film in on_slate)


def read(films, on):
    """The readouts of the film set `films` (any order, keys) under `on`, a `StoredVotes`."""
    slate = sorted(set(films), key=lambda film: on.rank[film])
    on_slate = set(slate)
    held = [each for each in on.records if each[1] in on_slate]
    on_the_ballot = set(on.candidates)
    ballot_records = [each for each in on.records if each[1] in on_the_ballot]
    runtimes = {film: on.runtimes[film] for film in slate}
    result = plans.plan(on.voters, slate, runtimes, held, on.floor_set, on.budget)
    broken = plans.breakdown(result, slate, runtimes, held, list(on.candidates), ballot_records)
    return Read(tuple(slate), result, broken, total(slate, held))


@dataclass(frozen=True)
class Standing:
    """A row's place among the rows on screen."""

    tier: int  # numbered from the best
    tied: int  # how many rows share the tier, itself included
    best: bool  # the best row on screen
    level: bool  # level with the best on floor and Σrep without being it
    objective: int  # W·m + Σrep
    floor_distance: object  # from the best row's floor, or None with no floor
    sigma_distance: int


def standings(rows, size, multiplier):
    """The standing of each of `rows`, (floor, Σrep, total) triples with floor None for an empty floor set, over a floor set of `size` voters.

    Tiers group rows equal on floor and Σrep and are numbered by `W·m + Σrep` from the best, `W = multiplier · size`;
    the best row has the highest of that, then the highest total, and nothing ranks rows within a tier (#17, #24, #33).
    """
    weight = multiplier * size
    objective = [(floor or 0) * weight + sigma for floor, sigma, _ in rows]
    chosen = max(range(len(rows)), key=lambda each: (objective[each], rows[each][2]), default=None)
    groups = {}
    for each, (floor, sigma, whole) in enumerate(rows):
        groups.setdefault((floor, sigma), []).append(each)
    ordered = sorted(groups, key=lambda key: (-objective[groups[key][0]], -max(rows[each][2] for each in groups[key])))
    tier_of = {key: place for place, key in enumerate(ordered, 1)}
    result = []
    for each, (floor, sigma, _) in enumerate(rows):
        key = (floor, sigma)
        best_floor, best_sigma, _ = rows[chosen]
        result.append(
            Standing(
                tier_of[key],
                len(groups[key]),
                each == chosen,
                each != chosen and key == (best_floor, best_sigma),
                objective[each],
                None if floor is None else floor - best_floor,
                sigma - best_sigma,
            )
        )
    return result


@dataclass(frozen=True)
class Dots:
    columns: tuple  # film keys: the core first, then the rest, each in slate order
    core: frozenset  # the films every row holds, empty with one row


def dots(sets, rank):
    """The dots' columns over any number of film sets, `rank` giving each film's place in slate order (#24, #36)."""
    sets = [set(each) for each in sets]
    union = set().union(*sets)
    core = frozenset(set.intersection(*sets)) if len(sets) > 1 else frozenset()
    return Dots(tuple(sorted(union, key=lambda film: (film not in core, rank[film]))), core)
