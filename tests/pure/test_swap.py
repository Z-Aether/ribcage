"""The swap between two slates, a pure function of two film sets and the stored votes (#24, #170)."""

from ribcage.readouts.basis import Basis
from ribcage.readouts.floor import FloorSet
from ribcage.readouts.ledger import stored_votes
from ribcage.readouts.swap import swap

TITLES = {"cube": "Cube", "thing": "The Thing", "alien": "Alien", "tron": "Tron"}
RUNTIMES = {"cube": 90, "thing": 109, "alien": 117, "tron": 96}
RECORDS = [
    ("ada", "cube", 3, False, False),
    ("ada", "thing", 1, False, False),
    ("dani", "thing", 2, False, False),
    ("dani", "cube", None, True, False),
    ("dani", "alien", 3, False, False),
]


def on(floor=None, basis=Basis(), voters=("ada", "dani")):
    return stored_votes(voters, floor or FloorSet(tuple(voters), ()), RECORDS, TITLES, RUNTIMES, set(TITLES), 600, basis)


def the_swap():
    return swap(["cube", "thing"], ["thing", "alien"], on())


def test_the_films_are_shared_out_and_in_each_in_slate_order():
    found = the_swap()

    assert found.shared == ("thing",)
    assert found.out == ("cube",)
    assert found.into == ("alien",)


def test_each_film_out_and_in_carries_its_points_and_whom_it_represented_or_becomes():
    found = the_swap()

    (out,), (into,) = found.carried_out, found.carried_in
    assert (out.film, out.points, out.represents) == ("cube", 1, (("ada", False),))
    assert (into.film, into.points, into.represents) == ("alien", 3, (("dani", False),))


def test_each_voters_representative_and_score_change_with_their_amount():
    ada, dani = the_swap().moves

    assert (ada.before.representative, ada.before.score, ada.after.representative, ada.after.score, ada.change) == ("cube", 3, "thing", 1, -2)
    assert (dani.before.representative, dani.after.representative, dani.change) == ("thing", "alien", 1)


def test_slate_sums_the_floor_and_the_pinners_before_and_after():
    found = the_swap()
    ada, dani = found.moves

    assert (ada.before.slate_sum, ada.after.slate_sum, ada.sum_change) == (4, 1, -3)
    assert (dani.before.slate_sum, dani.after.slate_sum, dani.sum_change) == (0, 5, 5)
    assert found.floor == (2, 1) and found.sigma_rep == (5, 4) and found.total == (4, 6)
    assert (ada.before.pins, ada.after.pins, dani.before.pins, dani.after.pins) == (False, True, True, False)
    assert found.screen_time == (199, 226)


def test_the_vetoes_on_each_slate():
    assert the_swap().vetoes == (1, 0)


def test_a_swap_of_a_slate_with_itself_changes_nothing():
    found = swap(["thing", "cube"], ["cube", "thing"], on())

    assert found.out == found.into == found.carried_out == found.carried_in == ()
    assert found.shared == ("thing", "cube")
    assert all(each.change == 0 and each.sum_change == 0 and each.before == each.after for each in found.moves)
    assert all(one == two for one, two in (found.floor, found.sigma_rep, found.total, found.screen_time, found.vetoes))


def test_a_voter_outside_the_floor_set_shows_the_reason_and_no_change():
    floor = FloorSet(("ada",), (("dani", "no ballot"),))

    _, dani = swap(["cube", "thing"], ["thing", "alien"], on(floor)).moves

    assert dani.out == "no ballot" and dani.change == 0


def test_a_voter_set_aside_by_a_knob_has_no_slate_sum():
    floor = FloorSet(("ada",), (("dani", "set aside by knob"),))

    _, dani = swap(["cube", "thing"], ["thing", "alien"], on(floor, Basis(without=frozenset({"dani"})))).moves

    assert dani.out == "set aside by knob"
    assert dani.before.slate_sum is None and dani.after.slate_sum is None and dani.sum_change is None


def test_disregarding_a_voters_vetoes_changes_the_swap():
    found = swap(["cube", "thing"], ["thing", "alien"], on(basis=Basis(disregarded=frozenset({"dani"}))))

    assert found.total[0] == 3 + 3
