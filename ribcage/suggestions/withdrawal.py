"""Withdraw: a suggester taking back their own suggestion while nothing yet depends on it, and what goes with it (#27, #34, #89)."""

from django.db.models import Exists, OuterRef

from ribcage.ballot.models import BallotRecord
from ribcage.suggestions.models import Approval


def with_holds(suggestions):
    """Every load of suggestions that feeds withdrawable goes through here, so M7 and M9 add their holds
    (a timetable box, a kept proposal) as annotations in this module alone (#34, #89, #118)."""
    return suggestions.annotate(held_by_ballot=Exists(BallotRecord.objects.filter(suggestion=OuterRef("pk"))))


def withdrawable(suggestion):
    """Whether nothing downstream holds the suggestion, so a withdraw can only take the film and its notes (#34).

    Reads only what the suggestion was loaded with, so the pool asks it of every card at no query each,
    and a later hold joins it as an annotation in `with_holds`. The runtime pencil reads it (#90), and so does the Films tab's runtime box before it clears one (#97).
    A suggestion loaded any other way has no annotation, and the read raises rather than call it unheld (#118).
    """
    # Read first, so an unloaded suggestion raises whatever its approval (#118).
    held = suggestion.held_by_ballot
    return suggestion.approval != Approval.APPROVED and not held


def may_withdraw(voter, suggestion):
    # Withdraw is the suggester's own; a removed suggester's blank link is no one's (#26, #27).
    return suggestion.suggester_id is not None and suggestion.suggester_id == voter.pk and withdrawable(suggestion)


def what_goes(notes_by_others):
    """What the confirm says goes with the film: the pitch, and the notes the group left on it (#89)."""
    if notes_by_others == 0:
        return "your pitch"
    notes = "one note" if notes_by_others == 1 else f"{notes_by_others} notes"
    return f"your pitch and {notes} from the group"


def withdraw(suggestion):
    # A withdrawn suggestion is simply gone, and its notes go with it (#26).
    suggestion.delete()
