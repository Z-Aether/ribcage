"""Removal: the admin taking a voter off the roster, and what the confirm says goes with them (#28, #79)."""

from django.db import transaction

from ribcage.suggestions import departure

# M6 extends both: scores, vetoes, done (#28). Everything that `on_delete` can express stays there (#98).


def what_goes(voter):
    """What the Roster tab's confirm lists as going with the voter, kept beside `remove` so the two stay in step."""
    notes, suggestions = departure.what_stays_and_goes(voter)
    goes = [
        "their display name and password",
        "their sessions, so they are signed out everywhere",
    ]
    if notes:
        goes.append("their one note on another film" if notes == 1 else f"their {notes} notes on other films")
    if suggestions:
        goes.append(
            "their suggestion stays, with its pitch, marked removed"
            if suggestions == 1
            else f"their {suggestions} suggestions stay, with their pitches, marked removed"
        )
    return goes


def remove(voter):
    # Their sessions hold only the row's id, so they end with it (#79).
    with transaction.atomic():
        departure.delete_notes_on_others_films(voter)
        voter.delete()
