"""Withdraw: a suggester taking back their own suggestion while nothing yet depends on it, and what goes with it (#27, #34, #89)."""

from django.db import transaction
from django.db.models import Count, Exists, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from ribcage.ballot.models import BallotRecord
from ribcage.suggestions.models import Approval
from ribcage.timetable.models import Box


def marks_by_others(field):
    # The group's marks on the film, the suggester's own left out, for the withdraw confirm (#151).
    counted = (
        BallotRecord.objects.filter(suggestion=OuterRef("pk"), **{field: True})
        .exclude(voter=OuterRef("suggester"))
        .values("suggestion")
        .annotate(n=Count("pk"))
        .values("n")
    )
    return Coalesce(Subquery(counted, output_field=IntegerField()), Value(0))


def with_holds(suggestions):
    """Every load of suggestions that feeds withdrawable goes through here, so M7 and M9 add their holds
    (a kept proposal) as annotations in this module alone (#34, #89, #118).
    Only a score holds a film from the ballot: a veto or seen it alone goes with a withdraw (#151)."""
    return suggestions.annotate(
        held_by_ballot=Exists(BallotRecord.objects.filter(suggestion=OuterRef("pk"), score__isnull=False)),
        vetoes_by_others=marks_by_others("vetoed"),
        seen_its_by_others=marks_by_others("seen_it"),
        held_by_box=Exists(Box.objects.filter(suggestion=OuterRef("pk"))),
    )


def withdrawable(suggestion):
    """Whether nothing downstream holds the suggestion, so a withdraw takes only the film, its notes and the unscored ballot records: vetoes and seen-its (#34, #151).

    Reads only what the suggestion was loaded with, so the pool asks it of every card at no query each,
    and a later hold joins it as an annotation in `with_holds`. The runtime pencil reads it (#90), and so does the Films tab's runtime box before it clears one (#97).
    A suggestion loaded any other way has no annotation, and the read raises rather than call it unheld (#118).
    """
    # Read first, so an unloaded suggestion raises whatever its approval (#118).
    held = suggestion.held_by_ballot
    held_by_box = suggestion.held_by_box
    return suggestion.approval != Approval.APPROVED and not held and not held_by_box


def may_withdraw(voter, suggestion):
    # Withdraw is the suggester's own; a removed suggester's blank link is no one's (#26, #27).
    return suggestion.suggester_id is not None and suggestion.suggester_id == voter.pk and withdrawable(suggestion)


def what_goes(notes_by_others, vetoes_by_others=0, seen_its_by_others=0):
    """What the confirm says goes with the film: the pitch, and the notes, vetoes and seen-its the group left on it (#89, #151)."""
    counts = [
        (notes_by_others, "one note", "notes"),
        (vetoes_by_others, "a veto", "vetoes"),
        (seen_its_by_others, "a seen-it flag", "seen-it flags"),
    ]
    parts = [one if count == 1 else f"{count} {many}" for count, one, many in counts if count]
    if not parts:
        return "your pitch"
    if len(parts) == 1:
        return f"your pitch and {parts[0]} from the group"
    return f"your pitch, {', '.join(parts[:-1])} and {parts[-1]} from the group"


def withdraw(suggestion):
    # A withdrawn suggestion is simply gone, and its notes and unscored records go with it (#26, #151).
    with transaction.atomic():
        BallotRecord.objects.filter(suggestion=suggestion, score__isnull=True).delete()
        suggestion.delete()
