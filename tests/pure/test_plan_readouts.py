"""The plan's set readouts, each trap from the catalogue over plain data (#10, #12, #147)."""

from ribcage.readouts.floor import FloorSet, floor_set
from ribcage.readouts.plan import clock, plan

RUNTIMES = {"cube": 90, "thing": 109, "alien": 117}
SLATE = ["cube", "thing"]


def read(records, slate=SLATE, voters=("ada", "dani"), members=None, budget=None, runtimes=RUNTIMES):
    found = FloorSet(tuple(voters if members is None else members), ())
    return plan(list(voters), slate, runtimes, [(voter, *each) for voter, *each in records], found, budget)


def row(result, voter):
    return next(each for each in result.rows if each.voter == voter)


def test_a_veto_and_a_seen_it_each_bar_a_film_from_representing():
    result = read([("ada", "cube", 3, True, False), ("ada", "thing", 2, False, False), ("dani", "cube", 3, False, True), ("dani", "thing", 1, False, False)])

    assert (row(result, "ada").representative, row(result, "ada").representation) == ("thing", 2)
    assert (row(result, "dani").representative, row(result, "dani").representation) == ("thing", 1)


def test_a_voters_best_is_the_highest_score_on_the_slate_alone():
    result = read([("ada", "cube", 1, False, False), ("ada", "thing", 3, False, False), ("ada", "alien", 3, False, False), ("dani", "alien", 3, False, False)])

    assert row(result, "ada").representative == "thing"
    assert (row(result, "dani").representative, row(result, "dani").representation) == (None, 0)


def test_representation_floors_at_zero_when_the_best_is_minus_one():
    result = read([("ada", "cube", -1, False, False), ("ada", "thing", 0, False, False)], voters=("ada",))

    assert (row(result, "ada").representative, row(result, "ada").representation) == (None, 0)
    assert result.floor == 0


def test_a_film_left_in_the_tray_and_a_vetos_minus_two_represent_nobody():
    result = read([("ada", "cube", None, True, False)], voters=("ada",))

    assert (row(result, "ada").representative, result.sigma_rep) == (None, 0)


def test_a_voter_outside_the_floor_set_never_sets_the_floor_and_shows_the_reason():
    found = FloorSet(("ada",), (("dani", "no ballot"),))
    result = plan(["ada", "dani"], SLATE, RUNTIMES, [("ada", "cube", 2, False, False)], found, None)

    assert (result.floor, result.sigma_rep) == (2, 2)
    assert (row(result, "dani").out, row(result, "dani").pins) == ("no ballot", False)


def test_a_dropped_film_on_the_slate_still_represents():
    # The floor set is over candidates; the slate holds a film that is no candidate, and it counts.
    found = floor_set(["ada"], {"cube": 90}, [("ada", "cube", 1, False, False)], None)
    result = plan(["ada"], ["cube", "dropped"], {"cube": 90, "dropped": 100}, [("ada", "cube", 1, False, False), ("ada", "dropped", 3, False, False)], found, None)

    assert (row(result, "ada").representative, row(result, "ada").representation) == ("dropped", 3)


def test_the_floor_pinner_is_starred_and_a_tie_stars_both():
    result = read([("ada", "cube", 3, False, False), ("dani", "cube", 1, False, False)])
    assert [(each.voter, each.pins) for each in result.rows] == [("ada", False), ("dani", True)]

    tie = read([("ada", "cube", 2, False, False), ("dani", "thing", 2, False, False)])
    assert [each.pins for each in tie.rows] == [True, True]


def test_an_empty_floor_set_has_no_floor():
    result = read([("ada", "cube", 3, False, False)], members=())

    assert (result.floor, result.sigma_rep) == (None, 0)
    assert not any(each.pins for each in result.rows)


def test_moving_boxes_changes_no_set_readout():
    records = [("ada", "cube", 3, False, False), ("dani", "thing", 1, True, False)]

    first, moved = read(records, ["cube", "thing"]), read(records, ["thing", "cube"])

    assert (first.rows, first.floor, first.sigma_rep, first.screen_time, first.films) == (moved.rows, moved.floor, moved.sigma_rep, moved.screen_time, moved.films)
    assert [each.film for each in first.vetoed] == ["thing"]


def test_vetoes_name_their_vetoers_in_voter_order_and_only_for_films_on_the_slate():
    result = read([("dani", "cube", None, True, False), ("ada", "cube", None, True, False), ("ada", "alien", None, True, False)])

    assert [(each.film, each.vetoers) for each in result.vetoed] == [("cube", ("ada", "dani"))]


def test_screen_time_is_over_only_past_the_budget():
    assert read([], budget=198).over
    assert not read([], budget=199).over
    assert not read([], budget=None).over


def test_the_clock_reads_hours_and_minutes():
    assert (clock(426), clock(540), clock(40), clock(0)) == ("7h06m", "9h", "40m", "0m")
