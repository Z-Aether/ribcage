"""The pool as voters read it: every suggestion as a film card, newest first, whatever its approval (#27)."""

from django.db.models import Prefetch

from ribcage.films import card
from ribcage.phase.order import Phase
from ribcage.suggestions import withdrawal
from ribcage.suggestions.models import Note, Suggestion

# Each pool phase's bar on the opened card: only SUGGEST's holds withdraw, so APPROVE's offers it nowhere (#27, #89).
PHASE_BARS = {
    Phase.SUGGEST: "components/suggest_bar.html",
    Phase.APPROVE: "components/approve_bar.html",
}


def notes_in_order():
    return Note.objects.select_related("author").order_by("pk")


def film_cards(viewer, phase):
    pool = withdrawal.with_holds(Suggestion.objects.prefetch_related(Prefetch("notes", queryset=notes_in_order()))).order_by("-pk")
    return [film_card(suggestion, suggestion.notes.all(), viewer, phase) for suggestion in pool]


def the_card(suggestion, viewer, phase):
    """One suggestion's card as the pool shows it to the viewer in the phase, to swap in where it was acted on (#88, #89)."""
    return film_card(suggestion, notes_in_order().filter(suggestion=suggestion), viewer, phase)


def film_card(suggestion, notes, viewer=None, phase=None):
    """The card for a suggestion and its notes, oldest first. The pitch is the note by the suggester, blank or not."""
    pitch = next((note for note in notes if note.author_id == suggestion.suggester_id), None)
    # A removed voter's notes on other films stay hidden until #98 deletes them (#28).
    others = tuple(card.Note(note.author.display_name, note.text) for note in notes if note is not pitch and note.author)
    return card.FilmCard(
        film=suggestion.film,
        suggester=suggestion.suggester_name,
        suggester_removed=suggestion.suggester_id is None,
        pitch=pitch.text if pitch else None,
        notes=others,
        suggestion_id=suggestion.pk,
        note_box=None if viewer is None else note_box(suggestion, notes, viewer),
        withdraw=offered_withdraw(suggestion, others, viewer),
        runtime_pencil=offered_pencil(suggestion, viewer, phase),
    )


def note_box(suggestion, notes, viewer):
    own = next((note for note in notes if note.author_id == viewer.pk), None)
    return card.NoteBox(text=own.text if own else "", is_pitch=suggestion.suggester_id == viewer.pk)


def offered_withdraw(suggestion, others, viewer):
    # Absent where it isn't allowed, with no explanation (#27).
    if viewer is None or not withdrawal.may_withdraw(viewer, suggestion):
        return None
    return card.Withdraw(goes=withdrawal.what_goes(len(others)))


def offered_pencil(suggestion, viewer, phase):
    # Any voter's in SUGGEST, on a film its suggester could still withdraw; absent elsewhere, with no explanation (#27, #34).
    if viewer is None or phase != Phase.SUGGEST or not withdrawal.withdrawable(suggestion):
        return None
    return card.RuntimePencil()
