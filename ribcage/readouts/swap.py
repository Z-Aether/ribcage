"""The swap between two slates read as one move: a pure function of two film sets and the stored votes under the basis (#24, #170)."""

from dataclasses import dataclass

from ribcage.readouts import ledger


@dataclass(frozen=True)
class Carried:
    """A film going out or coming in: its film points and whom it represents on the side that holds it, as (voter, pins)."""

    film: object
    runtime: int
    points: int
    represents: tuple


@dataclass(frozen=True)
class Side:
    """One voter's place on one side of the swap."""

    representative: object  # a film key, or None
    score: int
    pins: bool
    slate_sum: object  # an int, or None for a voter the knob set aside


@dataclass(frozen=True)
class Move:
    """What the swap does to one voter; `out` is the reason they are outside the floor set, who has no change."""

    voter: object
    before: Side
    after: Side
    out: str
    change: int  # the score after minus before, 0 for a voter outside the floor set
    sum_change: object  # the slate sum after minus before, or None where either is (a voter out for *nothing representable* has one, #177)


@dataclass(frozen=True)
class Swap:
    shared: tuple  # film keys in slate order
    out: tuple  # only on the left
    into: tuple  # only on the right
    carried_out: tuple
    carried_in: tuple
    floor: tuple  # (before, after), None with an empty floor set
    sigma_rep: tuple
    total: tuple
    screen_time: tuple  # minutes
    vetoes: tuple  # films vetoed on each slate
    moves: tuple


def swap(before, after, on):
    """The swap from the film set `before` to `after` (keys, any order) over `on`, a `ledger.StoredVotes`: films in slate order, the numbers, and every voter's move."""
    left, right = ledger.read(before, on), ledger.read(after, on)
    held_left, held_right = set(left.films), set(right.films)
    sides = lambda read: {each.voter: Side(each.representative, each.representation, each.pins, each.slate_sum) for each in read.breakdown.people}
    left_sides, right_sides = sides(left), sides(right)
    moves = []
    for was, now in zip(left.plan.rows, right.plan.rows):
        one, two = left_sides[was.voter], right_sides[was.voter]
        both = was.voter in left.plan.counted and two.slate_sum is not None and one.slate_sum is not None
        moves.append(Move(was.voter, one, two, was.out, 0 if was.out else two.score - one.score, two.slate_sum - one.slate_sum if both else None))
    return Swap(
        tuple(each for each in left.films if each in held_right),
        tuple(each for each in left.films if each not in held_right),
        tuple(each for each in right.films if each not in held_left),
        tuple(Carried(each.film, each.runtime, each.points, each.represents) for each in left.breakdown.films if each.film not in held_right),
        tuple(Carried(each.film, each.runtime, each.points, each.represents) for each in right.breakdown.films if each.film not in held_left),
        (left.plan.floor, right.plan.floor),
        (left.plan.sigma_rep, right.plan.sigma_rep),
        (left.total, right.total),
        (left.plan.screen_time, right.plan.screen_time),
        (len(left.plan.vetoed), len(right.plan.vetoed)),
        tuple(moves),
    )
