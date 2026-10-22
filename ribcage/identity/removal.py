"""Removal: the admin taking a voter off the roster, and what the confirm says goes with them (#28, #79)."""

from django.db import transaction

# M4 and M6 extend both: suggestions kept marked removed, notes on other films, scores, vetoes, done (#28).


def what_goes(voter):
    """What the Roster tab's confirm lists as going with the voter, kept beside `remove` so the two stay in step."""
    return [
        "their display name and password",
        "their sessions, so they are signed out everywhere",
    ]


def remove(voter):
    # Their sessions hold only the row's id, so they end with it (#79).
    with transaction.atomic():
        voter.delete()
