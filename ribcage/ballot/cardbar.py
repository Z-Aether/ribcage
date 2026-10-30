"""What the phase bar's row shows on a film's opened card, and who vetoes and has seen the film for its notes (#10, #35 §4, #122, #128, #150, #152, #153)."""

from django.db.models import Q

from ribcage.ballot.board import SCALE
from ribcage.ballot.models import BallotRecord
from ribcage.films.card import Marks, VoteBar


def of(viewer, suggestion):
    """The viewer's own score, veto and seen it (#122, #128)."""
    own = BallotRecord.objects.filter(voter=viewer, suggestion=suggestion).first()
    return VoteBar(scale=SCALE, score=own.score if own else None, vetoed=bool(own and own.vetoed), seen_it=bool(own and own.seen_it))


# The row outside VOTE for a film the viewer has marked nothing on: the veto and seen it, no scores (#152).
UNMARKED = VoteBar(scale=())


def marks_of(viewer):
    """The viewer's veto and seen it as SUGGEST's and APPROVE's row draws them, by suggestion id, in one query; a film they have no record on is `UNMARKED` (#152)."""
    records = BallotRecord.objects.filter(voter=viewer).values_list("suggestion_id", "vetoed", "seen_it")
    return {suggestion_id: VoteBar(scale=(), vetoed=vetoed, seen_it=seen_it) for suggestion_id, vetoed, seen_it in records}


def marks_on(viewer, suggestion):
    """The row outside VOTE for one film (#152)."""
    own = BallotRecord.objects.filter(voter=viewer, suggestion=suggestion).first()
    return VoteBar(scale=(), vetoed=own.vetoed, seen_it=own.seen_it) if own else UNMARKED


NO_MARKS = Marks()


def marks_by_film(suggestion_ids=None):
    """Who vetoes each film and who has seen it, every voter, the viewer and the admin's view alike, as {suggestion id: Marks}, in one query for the films named or all of them (#128, #153)."""
    records = BallotRecord.objects.filter(Q(vetoed=True) | Q(seen_it=True))
    if suggestion_ids is not None:
        records = records.filter(suggestion__in=suggestion_ids)
    found = {}
    for suggestion_id, voter_id, name, vetoed, seen_it in records.values_list("suggestion_id", "voter_id", "voter__display_name", "vetoed", "seen_it"):
        marks = found.setdefault(suggestion_id, Marks())
        if vetoed:
            marks.vetoers[voter_id] = name
        if seen_it:
            marks.seers[voter_id] = name
    return found
