"""Placing a film: the one way a score is set, and the one way it is cleared (#9, #118, #119)."""

from ribcage.ballot.board import SCALE
from ribcage.ballot.models import BallotRecord

UNSORTED = "unsorted"
SCORES = {str(score): score for score, *_ in SCALE}


def target_of(posted):
    """A score on the scale, or UNSORTED, from what a placement posted; None for anything else (#119)."""
    if posted == UNSORTED:
        return UNSORTED
    return SCORES.get(posted)


def place(voter, suggestion, target):
    """Put the voter's say on the suggestion at `target`, a score or UNSORTED. It names where the film is to be, so a repeat changes nothing.

    A score replaces a veto, and Unsorted clears both; a record left with no score, no veto and no seen it is deleted, so no record means untouched (#63, #118).
    """
    record = BallotRecord.objects.filter(voter=voter, suggestion=suggestion).first()
    score = None if target == UNSORTED else target
    if record is None:
        if score is not None:
            BallotRecord.objects.create(voter=voter, suggestion=suggestion, score=score)
        return
    record.score, record.vetoed, record.veto_reason = score, False, None
    if score is None and not record.seen_it:
        record.delete()
    else:
        record.save(update_fields=["score", "vetoed", "veto_reason"])
