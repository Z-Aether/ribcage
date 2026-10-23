"""What a removed voter leaves in the pool: their suggestions stay, their notes on other films go (#26, #28, #98)."""

from ribcage.suggestions.models import Note


def notes_on_others_films(voter):
    # The one rule `on_delete` can't express: a pitch is the author's note on their own suggestion (#26 §2).
    return Note.objects.filter(author=voter).exclude(suggestion__suggester=voter)


def what_stays_and_goes(voter):
    """(their notes on other films, their suggestions), the counts the Roster tab's confirm prints."""
    return notes_on_others_films(voter).count(), voter.suggestions.count()


def delete_notes_on_others_films(voter):
    """Called by `remove` before the voter row is deleted, while the author link still says whose each note is."""
    notes_on_others_films(voter).delete()
