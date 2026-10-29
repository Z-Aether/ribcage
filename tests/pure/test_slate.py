"""Film points and slate order (#24, #36, #137)."""

from ribcage.readouts.slate import SlateEntry, film_points, slate_order


def test_a_veto_counts_minus_two_and_an_unplaced_film_zero():
    assert film_points([(3, False), (-1, False), (None, True), (None, False)]) == 0
    assert film_points([(None, True), (None, True)]) == -4
    assert film_points([]) == 0


def test_film_points_sum_everyones_score():
    assert film_points([(3, False), (2, False), (0, False), (-1, False)]) == 4


def test_fewer_vetoes_come_first_whatever_the_points():
    order = slate_order([SlateEntry("loved", "A", 1, 20), SlateEntry("quiet", "B", 0, -3)])

    assert [each.key for each in order] == ["quiet", "loved"]


def test_then_more_points_then_title():
    order = slate_order([SlateEntry(1, "Cube", 0, 3), SlateEntry(2, "Alien", 0, 5), SlateEntry(3, "bat", 0, 3), SlateEntry(4, "Aliens", 0, 3)])

    assert [each.key for each in order] == [2, 4, 3, 1]
