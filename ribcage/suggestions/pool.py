"""The pool as voters read it: every suggestion as a film card, newest first, whatever its approval (#27)."""

from dataclasses import replace

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


# A film the voter tried to add when it was already in the pool: the next pool opens its card with their words (#26 §3, #93).
KEPT_FOR_ITS_CARD = "suggestions.kept_for_its_card"


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
    # The viewer's own note stays in the list, flagged: a collapsed card shows it, an opened one leaves it to their box (#88).
    others = tuple(
        card.Note(note.author.display_name, note.text, yours=viewer is not None and note.author_id == viewer.pk)
        for note in notes
        if note is not pitch and note.author
    )
    return card.FilmCard(
        film=suggestion.film,
        suggester=suggestion.suggester_name,
        suggester_removed=suggestion.suggester_id is None,
        pitch=pitch.text if pitch else None,
        notes=others,
        suggestion_id=suggestion.pk,
        mine=viewer is not None and suggestion.suggester_id == viewer.pk,
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


def keep_for_its_card(session, suggestion, typed):
    session[KEPT_FOR_ITS_CARD] = {"suggestion": suggestion.pk, "text": typed}


def kept_for_its_card(cards, session):
    """The cards with the one a voter's words were kept for holding them in its box, unsaved, and that card's id, or None (#93)."""
    kept = session.pop(KEPT_FOR_ITS_CARD, None)
    if kept is None or not cards or cards[0].note_box is None:
        return cards, None
    for index, card in enumerate(cards):
        if card.suggestion_id == kept["suggestion"]:
            box = with_kept_words(card, kept["text"])
            return [*cards[:index], replace(card, note_box=box), *cards[index + 1 :]], card.suggestion_id
    # Withdrawn since: the pool as it is now.
    return cards, None


def with_kept_words(card, typed):
    """The card's box with the typed words under whatever it already held, so Save loses neither (#93)."""
    said = "You've already suggested it" if card.mine else f"{card.suggester} suggested it first"
    box, words = card.note_box, typed.replace("\r\n", "\n").strip()
    if not words:
        return replace(box, refusal=f"{said}.", kept=True)
    if not box.text:
        return replace(box, text=words, refusal=f"{said}, so your words are here, not yet saved.", kept=True)
    under = "your pitch" if box.is_pitch else "your note"
    return replace(box, text=f"{box.text}\n\n{words}", refusal=f"{said}, so your words are under {under}, not yet saved.", kept=True)
