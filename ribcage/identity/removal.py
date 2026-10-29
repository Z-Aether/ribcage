"""Removal: the admin taking a voter off the roster, and what the confirm says goes with them (#28, #79)."""

from django.db import transaction

from ribcage.ballot import floor
from ribcage.ballot.models import BallotRecord, DoneMarker
from ribcage.suggestions import departure

# Everything that `on_delete` can express stays there, the ballot's records and done marker included (#98, #118).


def ballot_goes(voter):
    """What of the voter's ballot the confirm lists: each count only when present, then the done marker."""
    records = BallotRecord.objects.filter(voter=voter)
    counts = [
        (records.filter(score__isnull=False).count(), "score", "scores"),
        (records.filter(vetoed=True).count(), "veto", "vetoes"),
        (records.filter(seen_it=True).count(), "seen-it flag", "seen-it flags"),
    ]
    goes = []
    parts = [f"{count} {one if count == 1 else many}" for count, one, many in counts if count]
    if parts:
        goes.append("their " + (parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"))
    if DoneMarker.objects.filter(voter=voter).exists():
        goes.append("their done marker")
    return goes


def what_goes(voter):
    """What the Roster tab's confirm lists as going with the voter, kept beside `remove` so the two stay in step."""
    notes, suggestions = departure.what_stays_and_goes(voter)
    goes = [
        "their display name and password",
        "their sessions, so they are signed out everywhere",
    ]
    goes += ballot_goes(voter)
    if notes:
        goes.append("their one note on another film" if notes == 1 else f"their {notes} notes on other films")
    if suggestions:
        goes.append(
            "their suggestion stays, with its pitch, marked removed"
            if suggestions == 1
            else f"their {suggestions} suggestions stay, with their pitches, marked removed"
        )
    before, after = floor.change_on_removing(voter)
    goes.append(f"The floor set goes from {before.size} of {before.of} to {after.size} of {after.of}.")
    return goes


def remove(voter):
    # Their sessions hold only the row's id, so they end with it (#79).
    with transaction.atomic():
        departure.delete_notes_on_others_films(voter)
        voter.delete()
