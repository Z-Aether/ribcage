"""What the Phase tab says about each move: the act its confirm button names, and the consequences printed under it (#28, #77)."""

from typing import NamedTuple

from django.utils.html import format_html

from ribcage.phase.order import Phase, neighbours

SUGGEST, APPROVE, VOTE, PICK, RUN = Phase

# The confirm button names the act, not the destination (#28).
ACTS = {
    (SUGGEST, APPROVE): "Close suggestions",
    (APPROVE, SUGGEST): "Reopen suggestions",
    (APPROVE, VOTE): "Open the ballot",
    (VOTE, APPROVE): "Close the ballot",
    (VOTE, PICK): "Close VOTE and open the scores",
    (PICK, VOTE): "Reopen VOTE",
    (PICK, RUN): "Publish the plan",
    (RUN, PICK): "Unpublish",
}

# The heading of the page every voter sees in each phase; tests/http/test_phase.py pins it to the templates (#77).
VOTER_PAGES = {
    SUGGEST: "Suggest films",
    APPROVE: "Suggestions are closed",
    VOTE: "Vote",
    PICK: "Voting is closed",
    RUN: "The evening",
}


class OfferedMove(NamedTuple):
    to: Phase
    direction: str
    heading: str
    arm: str
    act: str
    consequences: list
    armed: bool


# Each direction's heading and arm-link wording, given the phase the move goes to (#28).
WORDINGS = {
    "back": ("◀ Back to {}", "◀ Move back to {}…"),
    "forward": ("Forward to {} ▶", "Move to {} ▶…"),
}


def consequences(from_phase, to_phase):
    # Later milestones add their sentences here: the reveal, reopened VOTE, publishing and the RUN purge (#77).
    return [format_html("Everyone's page becomes “{}”.", VOTER_PAGES[to_phase])]


def offered_move(phase, to, direction, armed_to):
    heading, arm = (wording.format(to) for wording in WORDINGS[direction])
    return OfferedMove(to, direction, heading, arm, ACTS[phase, to], consequences(phase, to), to == armed_to)


def offered(phase, armed_to=None):
    """One step back and one forward from the phase, or one at either end, with the one named by `armed_to` armed."""
    back, forward = neighbours(phase)
    return [offered_move(phase, to, direction, armed_to) for to, direction in [(back, "back"), (forward, "forward")] if to is not None]
