"""The tray's order: matched films first, each group in the voter's fixed shuffle (#38, #119)."""

from ribcage.ballot.order import shuffled, tray_order

FILMS = list(range(1, 31))


def test_matched_films_come_first_a_weak_match_included():
    order = tray_order(1, FILMS, matched_ids={7, 20, 3})

    assert set(order[:3]) == {7, 20, 3}
    assert set(order[3:]) == set(FILMS) - {7, 20, 3}


def test_it_is_the_same_on_every_call_for_a_voter_whatever_order_the_films_arrive_in():
    assert tray_order(1, FILMS, {4}) == tray_order(1, FILMS, {4}) == tray_order(1, FILMS[::-1], {4})


def test_it_differs_between_two_voters():
    assert tray_order(1, FILMS, set()) != tray_order(2, FILMS, set())


def test_adding_a_film_leaves_the_others_relative_order():
    before = tray_order(1, FILMS, {5})
    after = tray_order(1, [*FILMS, 99], {5})

    assert [film for film in after if film != 99] == before


def test_the_order_is_pinned_so_a_change_of_digest_is_noticed():
    assert shuffled(1, range(1, 8)) == [7, 4, 6, 5, 2, 3, 1]
