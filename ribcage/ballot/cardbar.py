"""What VOTE's phase bar shows on a film's opened card, and who vetoes the film for its notes (#10, #35 §4, #122, #128, #150)."""

from ribcage.ballot.board import SCALE
from ribcage.ballot.models import BallotRecord
from ribcage.films.card import VoteBar


def of(viewer, suggestion):
    """The viewer's own score, veto and seen it, and the names of the other voters who have seen the film, sorted by name (#122, #128)."""
    records = list(BallotRecord.objects.filter(suggestion=suggestion).select_related("voter"))
    own = next((record for record in records if record.voter_id == viewer.pk), None)
    others = sorted((record for record in records if record.voter_id != viewer.pk), key=lambda record: record.voter.display_name)
    return VoteBar(
        scale=SCALE,
        score=own.score if own else None,
        vetoed=bool(own and own.vetoed),
        seen_it=bool(own and own.seen_it),
        seen_by=tuple(record.voter.display_name for record in others if record.seen_it),
    )


def vetoers_on(suggestion):
    """Every voter who vetoes the film, the viewer included, as {voter id: name}, for the card's notes to mark (#10, #128)."""
    return dict(BallotRecord.objects.filter(suggestion=suggestion, vetoed=True).values_list("voter_id", "voter__display_name"))
