"""Withdraw's rules on plain data: which suggestions can be withdrawn, by whom, and what the confirm says goes (#27, #34, #89)."""

import pytest

from ribcage.films import card
from ribcage.identity.models import Voter
from ribcage.suggestions.models import Approval, Note, Suggestion, as_suggested
from ribcage.suggestions.pool import film_card
from ribcage.suggestions.withdrawal import may_withdraw, what_goes, withdrawable
from tests.films import THE_SHINING, as_loaded

ADA = Voter(pk=1, display_name="Ada")
BO = Voter(pk=2, display_name="Bo")


def a_suggestion(approval=Approval.UNDECIDED, suggester=ADA, held_by_ballot=False):
    suggestion = Suggestion(pk=10, suggester=suggester, suggester_name="Ada", approval=approval, **as_suggested(THE_SHINING))
    return as_loaded(suggestion, held_by_ballot)


@pytest.mark.parametrize(
    ("approval", "expected"),
    [(Approval.UNDECIDED, True), (Approval.APPROVED, False), (Approval.DROPPED, True)],
)
def test_a_suggestion_is_withdrawable_unless_approved(approval, expected):
    # A dropped film qualifies too, while nothing downstream holds it (#34).
    assert withdrawable(a_suggestion(approval)) is expected


def test_a_suggestion_with_a_ballot_record_is_not_withdrawable_whatever_its_approval():
    assert not withdrawable(a_suggestion(held_by_ballot=True))
    assert not withdrawable(a_suggestion(Approval.DROPPED, held_by_ballot=True))
    assert not may_withdraw(ADA, a_suggestion(held_by_ballot=True))


@pytest.mark.parametrize("approval", list(Approval))
def test_a_suggestion_not_loaded_through_with_holds_raises_rather_than_read_as_unheld(approval):
    # Approved too: approval must not short-circuit past the unloaded read (#118).
    unloaded = Suggestion(pk=10, suggester=ADA, suggester_name="Ada", approval=approval, **as_suggested(THE_SHINING))

    with pytest.raises(AttributeError):
        withdrawable(unloaded)


def test_the_suggester_may_withdraw_their_own():
    assert may_withdraw(ADA, a_suggestion())


def test_no_one_may_withdraw_another_voters_suggestion():
    assert not may_withdraw(BO, a_suggestion())


def test_the_suggester_may_not_withdraw_an_approved_one():
    assert not may_withdraw(ADA, a_suggestion(Approval.APPROVED))


def test_no_one_may_withdraw_a_removed_suggesters_suggestion():
    # A blank suggester link matches no voter, so a rejoined voter of the same name can't either (#26, #98).
    assert not may_withdraw(Voter(display_name="Ada"), a_suggestion(suggester=None))


@pytest.mark.parametrize(
    ("notes_by_others", "said"),
    [
        (0, "your pitch"),
        (1, "your pitch and one note from the group"),
        (3, "your pitch and 3 notes from the group"),
    ],
)
def test_what_goes_names_the_pitch_and_counts_the_groups_notes(notes_by_others, said):
    assert what_goes(notes_by_others) == said


@pytest.mark.parametrize(
    ("counts", "said"),
    [
        ((0, 1, 0), "your pitch and a veto from the group"),
        ((0, 0, 2), "your pitch and 2 seen-it flags from the group"),
        ((3, 2, 1), "your pitch, 3 notes, 2 vetoes and a seen-it flag from the group"),
        ((1, 0, 1), "your pitch, one note and a seen-it flag from the group"),
    ],
)
def test_what_goes_counts_the_groups_marks_as_it_counts_their_notes(counts, said):
    assert what_goes(*counts) == said


def test_the_card_offers_withdraw_on_the_viewers_own_withdrawable_suggestion():
    notes = [Note(author=ADA, text="Heeere's Johnny."), Note(author=BO, text="I'm in.")]

    shown = film_card(a_suggestion(), notes, viewer=ADA)

    assert shown.withdraw == card.Withdraw(goes="your pitch and one note from the group")


def test_the_card_offers_no_withdraw_on_another_voters_suggestion():
    assert film_card(a_suggestion(), [], viewer=BO).withdraw is None


def test_the_card_offers_no_withdraw_on_an_approved_suggestion():
    assert film_card(a_suggestion(Approval.APPROVED), [], viewer=ADA).withdraw is None


def test_without_a_viewer_the_card_offers_no_withdraw():
    assert film_card(a_suggestion(), []).withdraw is None
