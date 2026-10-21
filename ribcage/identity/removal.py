"""Removal: the admin taking a voter off the roster, the one routine later milestones extend with what goes with them (#28, #79)."""

from django.db import transaction


def remove(voter):
    """Deletes the voter's row, which ends their sessions, since each holds only its id (#79)."""
    # M4 keeps their suggestions and pitches, marked removed, and deletes their notes on other films; M6 their scores, vetoes and done marker (#28).
    with transaction.atomic():
        voter.delete()
