"""The plan's set readouts, each trap from the catalogue over plain data (#10, #12, #147)."""

from ribcage.readouts.floor import FloorSet, floor_set
from ribcage.readouts.plan import breakdown, clock, plan

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


def broken(records, slate=("cube", "thing"), candidates=("cube", "thing", "alien"), candidate_records=None, voters=("ada", "dani", "hanna"), members=None, out=()):
    found = FloorSet(tuple(voters if members is None else members), tuple(out))
    full = [(voter, *each) for voter, *each in records]
    read = plan(list(voters), list(slate), RUNTIMES, full, found, None)
    return breakdown(read, list(slate), RUNTIMES, full, list(candidates), full if candidate_records is None else [(voter, *each) for voter, *each in candidate_records])


def person(result, voter):
    return next(each for each in result.people if each.voter == voter)


def line(result, film):
    return next(each for each in result.films if each.film == film)


def test_film_points_sum_every_voter_with_a_veto_at_minus_two_and_an_unplaced_film_at_zero():
    result = broken([("ada", "cube", 3, False, False), ("dani", "cube", None, True, False), ("hanna", "cube", None, False, False), ("ada", "thing", 1, False, False)])

    assert line(result, "cube").points == 1
    assert line(result, "thing").points == 1
    assert line(result, "cube").likes == 1


def test_film_points_cover_a_voter_outside_the_floor_set():
    result = broken([("ada", "cube", 3, False, False), ("dani", "cube", 2, False, False)], members=("ada",), out=(("dani", "no ballot"),))

    assert line(result, "cube").points == 5


def test_the_film_with_the_most_points_is_flagged_and_a_film_representing_nobody_counts_those_who_like_it():
    result = broken([("ada", "cube", 3, False, False), ("ada", "thing", 1, False, False), ("dani", "thing", 2, False, False), ("dani", "cube", 3, True, False)], voters=("ada", "dani"))

    assert [(each.film, each.most) for each in result.films] == [("cube", False), ("thing", True)]
    assert line(result, "cube").represents == (("ada", False),)
    assert line(result, "thing").represents == (("dani", True),)
    nobody = broken([("ada", "cube", 3, False, False), ("dani", "cube", 2, False, False)], slate=("cube", "thing"))
    assert line(nobody, "thing").represents == () and line(nobody, "thing").likes == 0
    assert line(nobody, "cube").likes == 2


def test_a_slate_sum_counts_a_veto_as_minus_two():
    result = broken([("ada", "cube", 3, False, False), ("ada", "thing", None, True, False), ("dani", "cube", 1, False, False)])

    assert person(result, "ada").slate_sum == 1
    assert person(result, "dani").slate_sum == 1
    assert person(result, "hanna").slate_sum == 0


def test_a_voter_at_zero_gets_the_best_candidate_never_seen_vetoed_or_dropped():
    candidate_records = [
        ("ada", "alien", 3, False, True),  # seen
        ("ada", "ripley", 3, False, False),  # not a candidate: dropped
        ("ada", "blade", 2, True, False),  # vetoed
        ("ada", "tron", 1, False, False),
        ("ada", "cube", -1, False, False),
    ]
    result = broken(candidate_records, candidates=("alien", "blade", "tron", "cube"), candidate_records=[each for each in candidate_records if each[1] != "ripley"], voters=("ada",))

    assert person(result, "ada").best_eligible == ("tron", 1)
    assert person(result, "ada").representation == 0


def test_a_voter_at_zero_with_nothing_eligible_gets_none_and_a_represented_voter_gets_no_offer():
    result = broken([("ada", "cube", 2, False, False), ("dani", "alien", 0, False, False)], voters=("ada", "dani"))

    assert person(result, "ada").best_eligible is None
    assert person(result, "dani").best_eligible is None


def test_the_best_and_worst_served_slate_sums_are_marked_among_the_floor_set():
    result = broken(
        [("ada", "cube", 3, False, False), ("dani", "cube", 1, False, False), ("hanna", "cube", 2, False, False)],
        members=("ada", "dani", "hanna"),
    )

    assert [person(result, each).served for each in ("ada", "dani", "hanna")] == ["best", "worst", ""]
    even = broken([("ada", "cube", 1, False, False), ("dani", "cube", 1, False, False)], voters=("ada", "dani"))
    assert [each.served for each in even.people] == ["", ""]


def test_the_films_are_listed_in_the_slate_order_given():
    result = broken([], slate=("thing", "cube"))

    assert [each.film for each in result.films] == ["thing", "cube"]
