"""The pool as voters read it: every suggestion as a film card, newest first, whatever its approval (#27)."""

from dataclasses import replace

from django.db.models import Prefetch
from django.urls import reverse

from ribcage.ballot import cardbar
from ribcage.films import card
from ribcage.phase.order import Phase
from ribcage.suggestions import withdrawal
from ribcage.suggestions.models import Note, Suggestion
from ribcage.triggers import correction, stored, watched

# Each phase's bar on the opened card: only SUGGEST's holds withdraw, so APPROVE's offers it nowhere (#27, #89); VOTE's is the ballot's (#122).
PHASE_BARS = {
    Phase.SUGGEST: "components/suggest_bar.html",
    Phase.APPROVE: "components/approve_bar.html",
    Phase.VOTE: "components/vote_bar.html",
}


# A film the voter tried to add when it was already in the pool: the next pool opens its card with their words (#26 §3, #93).
KEPT_FOR_ITS_CARD = "suggestions.kept_for_its_card"


def notes_in_order():
    return Note.objects.select_related("author").order_by("pk")


def film_cards(viewer, phase):
    pool = list(withdrawal.with_holds(Suggestion.objects.prefetch_related(Prefetch("notes", queryset=notes_in_order()))).order_by("-pk"))
    loaded = stored.sections_and_matches_of(pool, watched.ticked_ids(viewer))
    # SUGGEST's and APPROVE's cards carry the viewer's veto and seen it; VOTE's are the ballot's (#152).
    marks, everyones = cardbar.marks_of(viewer), cardbar.marks_by_film()
    return [
        film_card(
            suggestion,
            suggestion.notes.all(),
            viewer,
            phase,
            listed_from(loaded[suggestion.pk][0], suggestion),
            loaded[suggestion.pk][1],
            marks.get(suggestion.pk, cardbar.UNMARKED),
            everyones.get(suggestion.pk, cardbar.NO_MARKS),
        )
        for suggestion in pool
    ]


def the_card(suggestion, viewer, phase):
    """One suggestion's card as the pool shows it to the viewer in the phase, to swap in where it was acted on (#88, #89)."""
    ((section, matched),) = stored.sections_and_matches_of([suggestion], watched.ticked_ids(viewer)).values()
    # VOTE's bar holds the viewer's own score, veto and seen it (#122); the other phases' row holds the veto and seen it (#152). Every voter's are in the notes (#153).
    vote = cardbar.of(viewer, suggestion) if phase == Phase.VOTE else cardbar.marks_on(viewer, suggestion)
    marks = cardbar.marks_by_film([suggestion.pk]).get(suggestion.pk, cardbar.NO_MARKS)
    return film_card(suggestion, notes_in_order().filter(suggestion=suggestion), viewer, phase, listed_from(section, suggestion), matched, vote, marks)


def listed_from(section, suggestion, route="dtdd_topics", corrects_at="dtdd_match"):
    """The section with its topic list left to fetch from the route as it first opens, so no page carries every film's list (#103),
    and its match line offering the paste-a-link control, which asks and saves at its own route (#105)."""
    topics_at = f"{reverse(route)}?suggestion={suggestion.pk}"
    return replace(section, topics_at=topics_at, correction=correction.offered(reverse(corrects_at)))


def film_card(suggestion, notes, viewer=None, phase=None, dtdd=None, matched=None, vote=None, marks=None):
    """The card for a suggestion and its notes, oldest first. The pitch is the note by the suggester, blank or not.

    Its DoesTheDogDie section is the same whoever views it, so the caller loads every card's at once (#103); the viewer's matched topics are theirs alone (#111).
    `marks` is who vetoes the film and who has seen it, on every card: a vetoer's note is marked and one with no note has a line of its own (#128); a seer's note ends in a 👁
    and those with no note and no veto gather on one line (#153).
    """
    marks = marks or card.Marks()
    vetoers, seers = marks.vetoers, marks.seers
    # Notes are written in the note box from SUGGEST through VOTE (#27, #150).
    boxed = viewer is not None
    pitch = next((note for note in notes if note.author_id == suggestion.suggester_id), None)
    # Removal deletes a voter's notes on other films, so every note but the pitch has an author (#98).
    # The viewer's own note stays in the list, flagged: a collapsed card shows it, an opened one leaves it to their box (#88).
    others = tuple(
        card.Note(note.author.display_name, note.text, yours=boxed and note.author_id == viewer.pk, vetoed=note.author_id in vetoers, seen=note.author_id in seers)
        for note in notes
        if note is not pitch
    )
    # A note with no text, a blank pitch, shows nowhere, so its vetoer gets a line of their own (#128).
    wrote = {note.author_id for note in notes if note.text}
    bare = tuple(
        card.Note(name, "", yours=boxed and voter_id == viewer.pk, vetoed=True, seen=voter_id in seers)
        for voter_id, name in sorted(vetoers.items(), key=lambda each: each[1].casefold())
        if voter_id not in wrote
    )
    # Seen it with no note and no veto: one line, by name (#153).
    seen_alone = sorted(((name, voter_id) for voter_id, name in seers.items() if voter_id not in wrote and voter_id not in vetoers), key=lambda each: each[0].casefold())
    return card.FilmCard(
        film=suggestion.film,
        suggester=suggestion.suggester_name,
        suggester_removed=suggestion.suggester_id is None,
        pitch=pitch.text if pitch else None,
        notes=others + bare,
        suggestion_id=suggestion.pk,
        mine=viewer is not None and suggestion.suggester_id == viewer.pk,
        note_box=note_box(suggestion, notes, viewer, vote) if boxed else None,
        vote=vote,
        withdraw=offered_withdraw(suggestion, others, viewer),
        runtime_pencil=offered_pencil(suggestion, viewer, phase),
        dtdd=dtdd,
        matched=matched,
        pitch_vetoed=pitch is not None and pitch.author_id in wrote and pitch.author_id in vetoers,
        pitch_seen=pitch is not None and pitch.author_id in wrote and pitch.author_id in seers,
        seen_by=tuple(name for name, _ in seen_alone),
        seen_by_others=tuple(name for name, voter_id in seen_alone if not boxed or voter_id != viewer.pk),
    )


def note_box(suggestion, notes, viewer, vote=None):
    own = next((note for note in notes if note.author_id == viewer.pk), None)
    return card.NoteBox(text=own.text if own else "", is_pitch=suggestion.suggester_id == viewer.pk, vetoed=vote is not None and vote.vetoed)


def offered_withdraw(suggestion, others, viewer):
    # Absent where it isn't allowed, with no explanation (#27).
    if viewer is None or not withdrawal.may_withdraw(viewer, suggestion):
        return None
    return card.Withdraw(goes=withdrawal.what_goes(len(others), suggestion.vetoes_by_others, suggestion.seen_its_by_others))


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
        return replace(box, text=words, was=box.text, refusal=f"{said}, so your words are here, not yet saved.", kept=True)
    under = "your pitch" if box.is_pitch else "your note"
    return replace(box, text=f"{box.text}\n\n{words}", was=box.text, refusal=f"{said}, so your words are under {under}, not yet saved.", kept=True)
