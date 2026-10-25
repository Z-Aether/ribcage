"""Placing a film: the one way a score or a veto is set, and the one way either is cleared (#9, #118, #119, #120)."""

from ribcage.ballot.board import SCALE, TRAY, VETOES
from ribcage.ballot.models import BallotRecord
from ribcage.suggestions.notes import note_text

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

    A score replaces a veto and Unsorted clears it, with its reason; a veto replaces a score and keeps a reason it already has.
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
    if not veto:
        record.veto_reason = None
    if score is None and not veto and not record.seen_it:
        record.delete()
    else:
        record.save(update_fields=["score", "vetoed", "veto_reason"])


def mark_seen(voter, suggestion, seen):
    """Set the voter's seen it on the suggestion to `seen`, leaving score and veto alone; a repeat changes nothing.

    A record left with nothing is deleted, as `place` does. Returns whether the voter vetoes the film, for the answer that redraws it (#10, #118, #121).
    """
    record = BallotRecord.objects.filter(voter=voter, suggestion=suggestion).first()
    if record is None:
        if seen:
            BallotRecord.objects.create(voter=voter, suggestion=suggestion, seen_it=True)
        return False
    record.seen_it = seen
    if not seen and record.score is None and not record.vetoed:
        record.delete()
    else:
        record.save(update_fields=["seen_it"])
    return record.vetoed


def give_reason(voter, suggestion, typed):
    """Keep the voter's reason on their veto as a note is kept, saving it empty clearing it; raises `TooLong` and writes nothing over the cap (#88, #120).

    Returns False where the voter has no veto on the film, as when a stale tab posts after the veto was dragged out.
    """
    vetoes = BallotRecord.objects.filter(voter=voter, suggestion=suggestion, vetoed=True)
    if not vetoes.exists():
        return False
    text = note_text(typed)
    vetoes.update(veto_reason=text or None)
    return True
