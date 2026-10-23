"""The pool as voters read it: every suggestion as a film card, newest first, whatever its approval (#27)."""

from django.db.models import Prefetch

from ribcage.films import card
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Note, Suggestion

# Each pool phase's bar on the opened card: SUGGEST's will also hold withdraw (#88, #89).
PHASE_BARS = {
    Phase.SUGGEST: "components/suggest_bar.html",
    Phase.APPROVE: "components/approve_bar.html",
}


def notes_in_order():
    return Note.objects.select_related("author").order_by("pk")


def film_cards(viewer):
    pool = Suggestion.objects.prefetch_related(Prefetch("notes", queryset=notes_in_order())).order_by("-pk")
    return [film_card(suggestion, suggestion.notes.all(), viewer) for suggestion in pool]


def the_card(suggestion, viewer):
    """One suggestion's card as the pool shows it to the viewer, to swap in where its note was saved (#88)."""
    return film_card(suggestion, notes_in_order().filter(suggestion=suggestion), viewer)


def film_card(suggestion, notes, viewer=None):
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
        suggestion_id=suggestion.pk,
        note_box=None if viewer is None else note_box(suggestion, notes, viewer),
    )


def note_box(suggestion, notes, viewer):
    own = next((note for note in notes if note.author_id == viewer.pk), None)
    return card.NoteBox(text=own.text if own else "", is_pitch=suggestion.suggester_id == viewer.pk)
