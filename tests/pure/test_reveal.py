"""The reveal's matrix over plain records (#154)."""

from ribcage.ballot import reveal
from ribcage.films.film import hand_entered

ADA, BO, CY = 1, 2, 3


def films(*titles):
    return [(index, hand_entered(title, 2020, 90)) for index, title in enumerate(titles, start=10)]


def built(voters, titles, records, reasons=None, viewer_id=ADA, sort=""):
    return reveal.build(voters, films(*titles), records, reasons or {}, viewer_id, sort)


def test_points_count_a_veto_at_minus_two_and_a_blank_at_zero():
    matrix = built([(ADA, "Ada", 1), (BO, "Bo", 1), (CY, "Cy", 0)], ["One"], [(ADA, 10, 3, False, False), (BO, 10, None, True, False)])

    assert matrix.rows[0].points == 1
    assert [cell.key for cell in matrix.rows[0].cells] == ["top-pick", "veto", "blank"]
    assert matrix.rows[0].cells[2].sign == ""


def test_rows_run_by_points_highest_first_and_ties_by_title():
    records = [(ADA, 10, 1, False, False), (ADA, 11, 3, False, False), (ADA, 12, 1, False, False), (ADA, 13, -1, False, False)]

    matrix = built([(ADA, "Ada", 4)], ["Zulu", "Echo", "alpha", "Bravo"], records)

    assert [row.film.title for row in matrix.rows] == ["Echo", "alpha", "Zulu", "Bravo"]


def test_a_voter_with_no_score_and_no_veto_didnt_vote_but_one_with_only_a_veto_did():
    records = [(BO, 10, None, True, False), (CY, 10, None, False, True)]

    matrix = built([(ADA, "Ada", 0), (BO, "Bo", 1), (CY, "Cy", 0)], ["One"], records)

    assert [column.didnt_vote for column in matrix.columns] == [True, False, True]


def test_a_partial_voter_reads_how_many_of_the_ballot_they_placed():
    titles = [f"Film {number}" for number in range(32)]

    matrix = built([(ADA, "Ada", 24), (BO, "Bo", 32), (CY, "Cy", 0)], titles, [(ADA, 10, 3, False, False)])

    assert [column.partial for column in matrix.columns] == ["24 of 32", "", ""]


def test_seen_it_rides_on_a_score_a_veto_and_a_blank_alike():
    records = [(ADA, 10, 2, False, True), (BO, 10, None, True, True), (CY, 10, None, False, True)]

    matrix = built([(ADA, "Ada", 1), (BO, "Bo", 1), (CY, "Cy", 0)], ["One"], records)

    assert [(cell.key, cell.seen_it) for cell in matrix.rows[0].cells] == [("keen", True), ("veto", True), ("blank", True)]


def test_a_vetoers_reason_is_on_their_cell_and_the_row_names_the_vetoers():
    records = [(ADA, 10, None, True, False), (BO, 10, None, True, False)]

    matrix = built([(ADA, "Ada", 1), (BO, "Bo", 1)], ["One"], records, {(ADA, 10): "Too far."})

    assert matrix.rows[0].vetoers == "Ada, Bo"
    assert "Too far." in matrix.rows[0].cells[0].meaning
    assert matrix.rows[0].points == -4


def test_only_the_viewers_column_is_theirs():
    matrix = built([(ADA, "Ada", 0), (BO, "Bo", 0)], ["One"], [], viewer_id=BO)

    assert [column.mine for column in matrix.columns] == [False, True]


def test_an_empty_ballot_is_an_empty_matrix():
    matrix = built([(ADA, "Ada", 0)], [], [])

    assert matrix.rows == ()
    assert matrix.columns[0].didnt_vote


def titles(matrix):
    return [row.film.title for row in matrix.rows]


BO_MARKS = [
    (BO, 10, None, True, False),
    (BO, 11, -1, False, False),
    (BO, 12, None, False, True),
    (BO, 13, 0, False, False),
    (BO, 14, 1, False, False),
    (BO, 15, 2, False, False),
    (BO, 16, 3, False, False),
]
NAMES = ["Veto", "Minus", "Blank", "Zero", "Plus1", "Plus2", "Plus3"]


def by_bo(sort):
    return built([(ADA, "Ada", 0), (BO, "Bo", 7)], NAMES, BO_MARKS, sort=sort)


def test_sorting_by_a_voter_runs_plus_three_down_to_zero_then_a_blank_then_minus_one_then_a_veto():
    assert titles(by_bo(str(BO))) == ["Plus3", "Plus2", "Plus1", "Zero", "Blank", "Minus", "Veto"]


def test_sorting_by_a_voter_reversed_runs_the_other_way():
    assert titles(by_bo(f"-{BO}")) == ["Veto", "Minus", "Blank", "Zero", "Plus1", "Plus2", "Plus3"]


def test_a_voters_ties_go_by_points_then_title():
    records = [(BO, 10, 1, False, False), (BO, 11, 1, False, False), (BO, 12, 1, False, False), (ADA, 12, 3, False, False), (ADA, 11, 3, False, False), (ADA, 10, 0, False, False)]

    matrix = built([(ADA, "Ada", 3), (BO, "Bo", 3)], ["Zulu", "Echo", "alpha"], records, sort=str(BO))

    # Bo scores all three alike; alpha and Echo tie on points, and both beat Zulu.
    assert titles(matrix) == ["alpha", "Echo", "Zulu"]


def test_sorting_by_film_runs_a_to_z_and_reversed_z_to_a():
    names = ["bravo", "Alpha", "Charlie"]

    assert titles(built([(ADA, "Ada", 0)], names, [], sort="film")) == ["Alpha", "bravo", "Charlie"]
    assert titles(built([(ADA, "Ada", 0)], names, [], sort="-film")) == ["Charlie", "bravo", "Alpha"]


def test_an_unknown_sort_or_voter_falls_back_to_points():
    records = [(ADA, 10, 1, False, False), (ADA, 11, 3, False, False)]
    default = titles(built([(ADA, "Ada", 2)], ["One", "Two"], records))

    for sort in ["", "points", "nonsense", "--points", "points-", "99", "-99", "-", "--film", "1.5", "٣"]:
        matrix = built([(ADA, "Ada", 2)], ["One", "Two"], records, sort=sort)
        assert titles(matrix) == default
        assert matrix.sort == ""
        assert all(column.marker == "" and column.aria_sort == "" for column in matrix.columns)
        assert matrix.film_marker == "" and matrix.film_aria_sort == ""
        assert (matrix.points_marker, matrix.points_aria_sort) == ("▾", "descending")


def test_the_active_column_wears_a_marker_and_its_link_reverses_while_the_others_sort_highest_first():
    voters = [(ADA, "Ada", 0), (BO, "Bo", 0)]

    up = built(voters, ["One"], [], sort=str(BO))
    assert [(column.marker, column.link) for column in up.columns] == [("", f"?sort={ADA}"), ("▾", f"?sort=-{BO}")]
    assert up.sort == str(BO)

    down = built(voters, ["One"], [], sort=f"-{BO}")
    assert [(column.marker, column.link) for column in down.columns][1] == ("▴", f"?sort={BO}")
    assert down.sort == f"-{BO}"

    assert (up.film_marker, up.film_link) == ("", "?sort=film")
    film = built(voters, ["One"], [], sort="film")
    assert (film.film_marker, film.film_link, film.sort) == ("▾", "?sort=-film", "film")
    assert built(voters, ["One"], [], sort="-film").film_marker == "▴"


def test_points_wears_the_marker_when_active_and_its_link_reverses_it():
    voters = [(ADA, "Ada", 0), (BO, "Bo", 0)]

    default = built(voters, ["One"], [])
    assert (default.points_marker, default.points_aria_sort, default.points_link, default.sort) == ("▾", "descending", "?sort=-points", "")
    assert built(voters, ["One"], [], sort="points").points_link == "?sort=-points"

    lowest = built(voters, ["One"], [], sort="-points")
    assert (lowest.points_marker, lowest.points_aria_sort, lowest.points_link, lowest.sort) == ("▴", "ascending", "?sort=", "-points")

    for sort in [str(BO), f"-{BO}", "film", "-film"]:
        sorted_by = built(voters, ["One"], [], sort=sort)
        assert (sorted_by.points_marker, sorted_by.points_aria_sort) == ("", "")
        assert sorted_by.points_link == "?sort="


def test_sorting_by_points_reversed_runs_lowest_first_with_ties_by_title_a_to_z():
    records = [(ADA, 10, 1, False, False), (ADA, 11, 3, False, False), (ADA, 12, 1, False, False), (ADA, 13, -1, False, False)]
    names = ["Zulu", "Echo", "alpha", "Bravo"]

    down = built([(ADA, "Ada", 4)], names, records)
    up = built([(ADA, "Ada", 4)], names, records, sort="-points")

    assert titles(down) == ["Echo", "alpha", "Zulu", "Bravo"]
    assert titles(up) == ["Bravo", "alpha", "Zulu", "Echo"]
    assert [row.points for row in up.rows] == [-1, 1, 1, 3]


def test_aria_sort_names_the_order_the_rows_run_in():
    voters = [(ADA, "Ada", 0), (BO, "Bo", 0)]

    # A voter's ▾ is highest first, which is descending; *Film*'s ▾ is A to Z, which is ascending.
    assert built(voters, ["One"], [], sort=str(BO)).columns[1].aria_sort == "descending"
    assert built(voters, ["One"], [], sort=f"-{BO}").columns[1].aria_sort == "ascending"
    assert built(voters, ["One"], [], sort="film").film_aria_sort == "ascending"
    assert built(voters, ["One"], [], sort="-film").film_aria_sort == "descending"
