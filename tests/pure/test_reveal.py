"""The reveal's matrix over plain records (#154)."""

from ribcage.ballot import reveal
from ribcage.films.film import hand_entered

ADA, BO, CY = 1, 2, 3


def films(*titles):
    return [(index, hand_entered(title, 2020, 90)) for index, title in enumerate(titles, start=10)]


def built(voters, titles, records, reasons=None, viewer_id=ADA):
    return reveal.build(voters, films(*titles), records, reasons or {}, viewer_id)


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
