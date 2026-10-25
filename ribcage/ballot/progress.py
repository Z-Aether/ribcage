"""How far each voter has got through the ballot, for every voter in one query: the Roster's columns and VOTE's consequences (#28, #124, #125)."""

from dataclasses import dataclass

from django.db.models import Count, Exists, OuterRef, Q

from ribcage.ballot.models import DoneMarker
from ribcage.identity.models import Voter
from ribcage.suggestions.models import Approval

# The SQL form of `board.is_placed`: a score or a veto, on a candidate (#119, #124).
PLACED = Q(ballot_records__suggestion__approval=Approval.APPROVED) & (Q(ballot_records__score__isnull=False) | Q(ballot_records__vetoed=True))
VETOED = Q(ballot_records__suggestion__approval=Approval.APPROVED, ballot_records__vetoed=True)


@dataclass(frozen=True)
class Progress:
    voter_id: int
    name: str
    # Candidates out of Unsorted, vetoes included; a dropped film's kept records don't count (#119).
    scored: int
    vetoes: int
    done: bool


def of_every_voter():
    """Every voter's Progress, in the Roster's case-blind order, for the admin alone; the ballot's size is `board.candidates().count()` (#35 §5, #124)."""
    voters = (
        Voter.objects.annotate(
            scored=Count("ballot_records", filter=PLACED),
            vetoes=Count("ballot_records", filter=VETOED),
            done=Exists(DoneMarker.objects.filter(voter=OuterRef("pk"))),
        )
        .order_by("display_name_key", "pk")
        .values_list("pk", "display_name", "scored", "vetoes", "done")
    )
    return tuple(Progress(*each) for each in voters)
