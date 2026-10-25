"""The done marker and the done roster: who has finished with the ballot, and nothing finer (#15, #26, #123)."""

from dataclasses import dataclass

from ribcage.ballot.models import DoneMarker
from ribcage.identity.models import Voter


@dataclass(frozen=True)
class Roster:
    # Every voter by name, each with whether they are done; the same for every viewer (#15, #35).
    names: tuple[tuple[str, bool], ...]
    # Whether the viewer is done, for their toggle.
    mine: bool = False

    @property
    def done(self):
        return sum(is_done for _, is_done in self.names)

    @property
    def size(self):
        return len(self.names)


def set_done(voter, done):
    """Set the voter's done marker to the state named; a repeat changes nothing (#15, #123)."""
    if done:
        DoneMarker.objects.get_or_create(voter=voter)
    else:
        DoneMarker.objects.filter(voter=voter).delete()


def roster(viewer):
    """The done roster: every voter by name, in the Roster tab's case-blind order, with a tick for each who is done (#15, #123)."""
    done_ids = set(DoneMarker.objects.values_list("voter_id", flat=True))
    voters = Voter.objects.order_by("display_name_key", "pk").values_list("pk", "display_name")
    return Roster(tuple((name, pk in done_ids) for pk, name in voters), viewer.pk in done_ids)
