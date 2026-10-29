"""The floor set: each trap from #15 and #33, over plain data (#146)."""

from ribcage.readouts.floor import NO_BALLOT, NOTHING_REPRESENTABLE, floor_set

RUNTIMES = {"short": 90, "long": 200}


def out(records, budget=None, runtimes=RUNTIMES):
    return dict(floor_set(["ada"], runtimes, [("ada", *each) for each in records], budget).out)


def test_a_voter_with_no_records_is_out_with_no_ballot():
    assert out([]) == {"ada": NO_BALLOT}


def test_a_seen_it_only_record_is_no_ballot():
    assert out([("short", None, False, True)]) == {"ada": NO_BALLOT}


def test_a_veto_only_voter_has_a_ballot_and_nothing_representable():
    assert out([("short", None, True, False)]) == {"ada": NOTHING_REPRESENTABLE}


def test_only_scores_of_zero_or_minus_one_is_nothing_representable():
    assert out([("short", 0, False, False), ("long", -1, False, False)]) == {"ada": NOTHING_REPRESENTABLE}


def test_every_positive_film_seen_or_vetoed_is_out():
    assert out([("short", 3, False, True), ("long", 2, True, False)]) == {"ada": NOTHING_REPRESENTABLE}


def test_a_positive_score_only_on_a_dropped_film_is_out():
    assert out([("gone", 3, False, False)]) == {"ada": NO_BALLOT}
    assert out([("gone", 3, False, False), ("short", 0, False, False)]) == {"ada": NOTHING_REPRESENTABLE}


def test_a_positive_film_over_the_budget_alone_is_out_and_in_with_no_budget():
    records = [("long", 3, False, False)]

    assert out(records, budget=199) == {"ada": NOTHING_REPRESENTABLE}
    assert out(records, budget=200) == {}
    assert out(records, budget=None) == {}


def test_one_representable_film_is_in():
    found = floor_set(["ada"], RUNTIMES, [("ada", "short", 1, False, False), ("ada", "long", -1, False, False)], 100)

    assert found.members == ("ada",) and found.out == () and (found.size, found.of) == (1, 1)


def test_the_sets_come_in_the_voters_order():
    found = floor_set(["c", "a", "b"], RUNTIMES, [("a", "short", 3, False, False)], None)

    assert found.members == ("a",)
    assert found.out == (("c", NO_BALLOT), ("b", NO_BALLOT))
