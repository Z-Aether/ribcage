"""Writing a voter's own note: one per voter per suggestion, cleared by saving it empty, except the pitch (#21, #26, #88)."""

from django.conf import settings

from ribcage.suggestions.models import Note


class TooLong(ValueError):
    def __init__(self, length, cap):
        super().__init__(f"{length} characters, over the cap of {cap}")
        self.length = length
        self.cap = cap


class PitchRequired(ValueError):
    pass


def note_text(typed):
    """The note as it is kept: trimmed, with a browser's CRLF as one break, refused whole over the cap, never cut (#88)."""
    text = typed.replace("\r\n", "\n").strip()
    if len(text) > settings.NOTE_MAX_LENGTH:
        raise TooLong(len(text), settings.NOTE_MAX_LENGTH)
    return text


def write(suggestion, author, typed):
    """Save the author's own note on the suggestion; an empty one deletes it, but a pitch can't be emptied (#88).

    Only the author's own note is ever touched, so no voter can edit another's.
    """
    text = note_text(typed)
    if text:
        Note.objects.update_or_create(suggestion=suggestion, author=author, defaults={"text": text})
    elif suggestion.suggester_id == author.pk:
        # A suggestion's pitch is required; withdrawing is how a suggester takes the film back (the dev, 2026-10-22; #89).
        raise PitchRequired
    else:
        Note.objects.filter(suggestion=suggestion, author=author).delete()
