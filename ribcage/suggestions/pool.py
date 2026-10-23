"""The pool as voters read it: every suggestion as a film card, newest first, whatever its approval (#27)."""

from django.db.models import Prefetch

from ribcage.films import card
from ribcage.suggestions.models import Note, Suggestion


def film_cards():
    notes = Prefetch("notes", queryset=Note.objects.select_related("author").order_by("pk"))
    pool = Suggestion.objects.prefetch_related(notes).order_by("-pk")
    return [film_card(suggestion, suggestion.notes.all()) for suggestion in pool]


def film_card(suggestion, notes):
    """The card for a suggestion and its notes, oldest first. The pitch is the note by the suggester, blank or not."""
    pitch = next((note for note in notes if note.author_id == suggestion.suggester_id), None)
    return card.FilmCard(
        film=suggestion.film,
        suggester=suggestion.suggester_name,
        suggester_removed=suggestion.suggester_id is None,
        pitch=pitch.text if pitch else None,
        # A removed voter's notes on other films stay hidden until #98 deletes them (#28).
        notes=tuple(
            card.Note(note.author.display_name, note.text) for note in notes if note is not pitch and note.author
        ),
    )
