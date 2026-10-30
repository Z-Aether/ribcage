"""Placing a film: the one way a score or a veto is set, and the one way either is cleared (#9, #118, #119, #120)."""

from ribcage.ballot.board import SCALE, TRAY, VETOES
from ribcage.ballot.models import BallotRecord
from ribcage.suggestions.models import Note

UNSORTED = TRAY
VETO = VETOES
SCORES = {str(score): score for score, *_ in SCALE}


def target_of(posted):
    """A score on the scale, UNSORTED or VETO, from what a placement posted; None for anything else (#119, #120)."""
    if posted in (UNSORTED, VETO):
        return posted
    return SCORES.get(posted)


def place(voter, suggestion, target):
    """Put the voter's say on the suggestion at `target`: a score, UNSORTED or VETO. It names where the film is to be, so a repeat changes nothing.

    A score replaces a veto, and Unsorted clears it; a veto replaces a score. None of them touches a note, which a veto's reason is (#128).
    A record left with no score, no veto and no seen it is deleted, so no record means untouched (#10, #63, #118, #120).
    """
    record = BallotRecord.objects.filter(voter=voter, suggestion=suggestion).first()
    veto = target == VETO
    score = target if isinstance(target, int) else None
    if record is None:
        if score is not None or veto:
            BallotRecord.objects.create(voter=voter, suggestion=suggestion, score=score, vetoed=veto)
        return
    record.score, record.vetoed = score, veto
    if score is None and not veto and not record.seen_it:
        record.delete()
    else:
        record.save(update_fields=["score", "vetoed"])


def mark_seen(voter, suggestion, seen):
    """Set the voter's seen it on the suggestion to `seen`, leaving score and veto alone; a repeat changes nothing.

    A record left with nothing is deleted, as `place` does (#10, #118, #121).
    """
    record = BallotRecord.objects.filter(voter=voter, suggestion=suggestion).first()
    if record is None:
        if seen:
            BallotRecord.objects.create(voter=voter, suggestion=suggestion, seen_it=True)
        return
    record.seen_it = seen
    if not seen and record.score is None and not record.vetoed:
        record.delete()
    else:
        record.save(update_fields=["seen_it"])


def needs_a_reason(voter, suggestion):
    """Whether a veto just made has no note of the voter's to be its reason yet, so its card opens for one: on their own suggestion the pitch is the note (#120, #128)."""
    return not Note.objects.filter(author=voter, suggestion=suggestion).exists()

