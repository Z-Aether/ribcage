"""The slate ledger's readouts over plain data, each trap from the ticket (#6, #17, #24, #33, #164)."""

from ribcage.readouts.floor import FloorSet
from ribcage.readouts.ledger import stored_votes, dots, read, standings, total
from ribcage.readouts.slate import film_points

TITLES = {"cube": "Cube", "thing": "The Thing", "alien": "Alien", "tron": "Tron"}
RUNTIMES = {"cube": 90, "thing": 109, "alien": 117, "tron": 96}
RECORDS = [
    ("ada", "cube", 3, False, False),
    ("ada", "thing", 1, False, False),
    ("dani", "thing", 2, False, False),
    ("dani", "cube", None, True, False),
    ("dani", "alien", 3, False, False),
]


def on(records=RECORDS, voters=("ada", "dani"), members=None, budget=None):
    found = FloorSet(tuple(voters if members is None else members), ())
    return stored_votes(voters, found, records, TITLES, RUNTIMES, set(TITLES), budget)


def test_the_total_counts_a_veto_minus_two_and_an_unplaced_film_zero_and_is_the_sum_of_the_film_points():
    result = read(["cube", "thing", "tron"], on())

    assert total(["cube", "thing", "tron"], RECORDS) == (3 - 2) + (1 + 2) + 0
    assert result.total == sum(each.points for each in result.breakdown.films)
    assert result.total == sum(film_points([(score, vetoed) for _, film, score, vetoed, _ in RECORDS if film == key]) for key in ("cube", "thing", "tron"))


def test_the_films_of_a_row_come_in_slate_order_whatever_order_they_were_given():
    assert read(["cube", "thing"], on()).films == read(["thing", "cube"], on()).films == ("thing", "cube")


def test_the_best_row_is_the_highest_objective_then_the_highest_total():
    rows = [(1, 5, 10), (2, 2, 3), (1, 5, 12), (2, 2, 1)]  # objectives with W = 2: 7, 6, 7, 6

    stood = standings(rows, 2, 1)

    assert [each.best for each in stood] == [False, False, True, False]


def test_rows_equal_on_floor_and_sigma_rep_share_a_tier_and_read_tied_whatever_their_totals():
    stood = standings([(2, 5, 1), (2, 5, 40), (1, 4, 9)], 3, 1)

    assert stood[0].tier == stood[1].tier and stood[0].tied == stood[1].tied == 2
    assert stood[2].tied == 1
    assert stood[0].level and stood[1].best


def test_tiers_are_numbered_by_the_objective_from_the_best():
    stood = standings([(0, 9, 0), (2, 1, 0), (1, 5, 0)], 3, 1)  # 9, 7, 8

    assert [each.tier for each in stood] == [1, 3, 2]


def test_distances_are_measured_from_the_best():
    stood = standings([(2, 4, 0), (3, 6, 0), (2, 4, 0)], 2, 1)

    assert (stood[0].floor_distance, stood[0].sigma_distance) == (-1, -2)
    assert (stood[1].floor_distance, stood[1].sigma_distance) == (0, 0)


def test_the_total_distance_is_measured_from_the_best_rows_total():
    stood = standings([(2, 4, 7), (3, 6, 5), (3, 6, 9)], 2, 1)  # the best is the highest total of the best objective

    assert [each.total_distance for each in stood] == [-2, -4, 0]


def test_a_single_row_is_the_best_and_alone_in_its_tier():
    only = standings([(1, 3, 4)], 2, 1)[0]

    assert (only.tier, only.tied, only.best, only.level) == (1, 1, True, False)


def test_an_empty_floor_set_gives_no_floor_and_still_ranks():
    found = FloorSet((), ())
    result = read(["cube", "thing"], stored_votes(("ada",), found, RECORDS, TITLES, RUNTIMES, set(TITLES), None))
    stood = standings([(result.plan.floor, 4, 2), (None, 7, 1)], 0, 1)

    assert result.plan.floor is None
    assert [each.tier for each in stood] == [2, 1] and stood[1].floor_distance is None


def test_the_core_is_empty_with_one_row_and_holds_exactly_what_every_row_holds_with_several():
    rank = {"cube": 0, "thing": 1, "alien": 2, "tron": 3}

    assert dots([{"cube", "thing"}], rank).core == frozenset()
    several = dots([{"cube", "thing", "tron"}, {"thing", "alien", "tron"}, {"tron", "thing"}], rank)

    assert several.core == {"thing", "tron"}


def test_the_dots_put_the_core_first_then_the_rest_each_in_slate_order():
    rank = {"cube": 0, "thing": 1, "alien": 2, "tron": 3}

    assert dots([{"cube", "tron", "alien"}, {"alien", "tron", "thing"}], rank).columns == ("alien", "tron", "cube", "thing")
    assert dots([{"tron", "cube"}], rank).columns == ("cube", "tron")
    assert dots([], rank).columns == ()


def test_the_tiers_order_on_any_comparable_key_not_only_a_number():
    from dataclasses import dataclass

    @dataclass(frozen=True, order=True)
    class Key:  # stands for #176's tuple keys: ordered, not negatable
        part: int

        def __sub__(self, other):
            return self.part - other.part

    stood = standings([(2, 5, Key(1)), (2, 5, Key(9)), (1, 4, Key(3))], 3, 1)

    assert [each.tier for each in stood] == [1, 1, 2]
    assert stood[1].best
