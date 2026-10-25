"""What VOTE's phase bar shows on a film's opened card (#10, #35 §4, #122)."""

from ribcage.ballot.board import SCALE
from ribcage.ballot.models import BallotRecord
from ribcage.films.card import Vetoer, VoteBar


def of(viewer, suggestion):
    """The viewer's own score, veto, reason and seen it, and the names of the other voters who vetoed the film or have seen it, sorted by name (#122)."""
    records = list(BallotRecord.objects.filter(suggestion=suggestion).select_related("voter"))
    own = next((record for record in records if record.voter_id == viewer.pk), None)
    others = sorted((record for record in records if record.voter_id != viewer.pk), key=lambda record: record.voter.display_name)
    return VoteBar(
        scale=SCALE,
        score=own.score if own else None,
        vetoed=bool(own and own.vetoed),
        reason=(own.veto_reason or "") if own else "",
        seen_it=bool(own and own.seen_it),
        vetoed_by=tuple(Vetoer(record.voter.display_name, record.veto_reason or "") for record in others if record.vetoed),
        seen_by=tuple(record.voter.display_name for record in others if record.seen_it),
    )
