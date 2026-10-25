"""VOTE's moves: the reveal's confirm, the reopened line and what the other two moves keep (#15, #28, #29, #125)."""

import pytest

from ribcage.ballot.done import set_done
from ribcage.ballot.models import BallotRecord
from ribcage.ballot.reopened import LINE
from ribcage.phase.history import move
from ribcage.phase.order import Phase
from tests.http.test_ballot_page import film, signed_in
from tests.http.test_phase import walk_to
from tests.http.test_phase_tab import armed, moves, text

SUGGEST, APPROVE, VOTE, PICK, RUN = Phase


@pytest.fixture
def vote(voters):
    """VOTE is open on four films: Hanna has scored three, ada one, Dani nothing."""
    walk_to(VOTE)
    films = [film(voters["Hanna"], f"Film {n}") for n in range(4)]
    for who, count in [("Hanna", 3), ("ada", 1)]:
        for each in films[:count]:
            BallotRecord.objects.create(voter=voters[who], suggestion=each, score=2)
    return voters


def consequences(admin, from_phase, to_phase):
    return text(moves(armed(admin, from_phase, to_phase))[str(to_phase)])


def test_the_reveal_names_who_is_not_done_with_their_progress(admin, vote):
    set_done(vote["ada"], True)

    said = consequences(admin, VOTE, PICK)

    assert "Not done yet: Dani nothing scored · Hanna 3/4." in said
    assert "ada" not in said.split("Not done yet:")[1].split(".")[0]


def test_a_vote_counts_as_progress(admin, vote):
    BallotRecord.objects.create(voter=vote["Dani"], suggestion=film(vote["Hanna"], "Fifth"), vetoed=True)

    assert "Dani 1/5" in consequences(admin, VOTE, PICK)


def test_the_reveal_says_when_everyone_is_done(admin, vote):
    for each in vote.values():
        set_done(each, True)

    said = consequences(admin, VOTE, PICK)

    assert "Everyone is done." in said and "Not done yet" not in said


def test_the_reveal_says_it_cannot_be_taken_back(admin, vote):
    assert "This can't be taken back: going back to VOTE hides the scores again, but everyone will have seen them." in consequences(admin, VOTE, PICK)


def test_the_reveal_box_alone_is_marked_to_turn_red_when_armed(admin, vote):
    assert 'phase-move--irreversible is-armed" data-to="PICK"' in armed(admin, VOTE, PICK)
    assert 'phase-move--back is-armed" data-to="APPROVE"' in armed(admin, VOTE, APPROVE)


def test_reopening_says_done_markers_stay_and_quotes_the_line(admin, vote):
    move(VOTE, PICK)

    said = consequences(admin, PICK, VOTE)

    assert "Done markers stay." in said and LINE in said


def test_closing_the_ballot_says_everything_is_kept(admin, vote):
    assert "Every score, veto and done marker is kept." in consequences(admin, VOTE, APPROVE)


def ballot_of(voter):
    return signed_in(voter).get("/").text


def test_the_ballot_carries_the_line_after_vote_pick_vote(vote):
    move(VOTE, PICK)
    move(PICK, VOTE)

    assert LINE in ballot_of(vote["ada"]).replace("&#x27;", "'")


def test_the_line_stands_above_the_board_and_after_the_header(vote):
    move(VOTE, PICK)
    move(PICK, VOTE)

    page = ballot_of(vote["ada"])

    assert page.index("</header>") < page.index("ballot-reopened") < page.index('class="tray')


def test_the_ballot_has_no_line_on_a_first_vote(vote):
    assert "ballot-reopened" not in ballot_of(vote["ada"])


def test_the_ballot_has_no_line_after_vote_approve_vote(vote):
    move(VOTE, APPROVE)
    move(APPROVE, VOTE)

    assert "ballot-reopened" not in ballot_of(vote["ada"])


def test_the_line_carries_no_time_and_says_nobody_looked(vote):
    move(VOTE, PICK)
    move(PICK, VOTE)

    assert "<time" not in ballot_of(vote["ada"]).split("ballot-reopened")[1].split("</p>")[0]
