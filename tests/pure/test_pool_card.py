"""The binding from a suggestion and its notes to the film card's plain data (#26, #57)."""

import dataclasses

from ribcage.films import card
from ribcage.films.film import RuntimeSource
from ribcage.identity.models import Voter
from ribcage.suggestions.models import Note, Suggestion, as_suggested
from ribcage.suggestions.pool import film_card
from tests.films import CABINET_OF_CURIOSITIES, THE_SHINING

ADA = Voter(pk=1, display_name="Ada")
BO = Voter(pk=2, display_name="Bo")
CY = Voter(pk=3, display_name="Cy")


def a_suggestion(film=THE_SHINING, suggester=ADA, suggester_name="Ada", **fields):
    return Suggestion(pk=10, suggester=suggester, suggester_name=suggester_name, **{**as_suggested(film), **fields})


def a_note(author, text):
    return Note(author=author, text=text)


def test_the_pitch_comes_first_whatever_order_the_notes_come_in():
    notes = [a_note(BO, "I'm in."), a_note(ADA, "Heeere's Johnny."), a_note(CY, "Lights off.")]

    shown = film_card(a_suggestion(), notes)

    assert shown.pitch == "Heeere's Johnny."
    assert shown.notes == (card.Note("Bo", "I'm in."), card.Note("Cy", "Lights off."))


def test_the_card_names_its_suggester_and_carries_the_film_as_suggested():
    shown = film_card(a_suggestion(), [a_note(ADA, "Heeere's Johnny.")])

    assert (shown.suggester, shown.suggester_removed) == ("Ada", False)
    assert shown.film == THE_SHINING
    assert shown.notes == ()


def test_a_blank_suggester_link_reads_as_removed_with_the_kept_name_and_the_pitch_still_first():
    notes = [a_note(BO, "I'm in."), a_note(None, "Just the one episode.")]

    shown = film_card(a_suggestion(CABINET_OF_CURIOSITIES, suggester=None, suggester_name="Ivo"), notes)

    assert (shown.suggester, shown.suggester_removed) == ("Ivo", True)
    assert shown.pitch == "Just the one episode."
    assert shown.notes == (card.Note("Bo", "I'm in."),)


def test_a_removed_voters_note_on_another_voters_film_is_not_shown():
    notes = [a_note(ADA, "Heeere's Johnny."), a_note(None, "I'm in.")]

    shown = film_card(a_suggestion(), notes)

    assert shown.pitch == "Heeere's Johnny."
    assert shown.notes == ()


def test_a_runtime_tmdb_gave_reads_as_tmdbs():
    assert film_card(a_suggestion(), []).film.runtime_source is RuntimeSource.TMDB


def test_a_runtime_changed_from_tmdbs_reads_as_by_hand():
    shown = film_card(a_suggestion(runtime=150), [])

    assert (shown.film.runtime, shown.film.runtime_source) == (150, RuntimeSource.HAND_ENTERED)


def test_a_hand_entered_film_reads_back_as_hand_entered():
    shown = film_card(a_suggestion(CABINET_OF_CURIOSITIES), [])

    assert shown.film == CABINET_OF_CURIOSITIES


def test_a_film_tmdb_gave_no_runtime_reads_as_by_hand_once_given_one():
    no_runtime = dataclasses.replace(THE_SHINING, runtime=None)

    shown = film_card(a_suggestion(no_runtime, runtime=144), [])

    assert (shown.film.runtime, shown.film.runtime_source) == (144, RuntimeSource.HAND_ENTERED)


def test_every_director_reads_back_in_order():
    codirected = dataclasses.replace(THE_SHINING, directors=("Severin Fiala", "Veronika Franz"))

    assert film_card(a_suggestion(codirected), []).film.directors == ("Severin Fiala", "Veronika Franz")


def test_the_card_carries_its_suggestions_key():
    assert film_card(a_suggestion(), []).suggestion_id == 10


def test_without_a_viewer_the_card_has_no_note_box():
    assert film_card(a_suggestion(), [a_note(BO, "I'm in.")]).note_box is None


def test_the_note_box_holds_the_viewers_own_note():
    notes = [a_note(ADA, "Heeere's Johnny."), a_note(BO, "I'm in."), a_note(CY, "Lights off.")]

    assert film_card(a_suggestion(), notes, viewer=BO).note_box == card.NoteBox(text="I'm in.", is_pitch=False)


def test_the_note_box_is_empty_for_a_viewer_with_no_note():
    assert film_card(a_suggestion(), [a_note(ADA, "Heeere's Johnny.")], viewer=CY).note_box == card.NoteBox(
        text="", is_pitch=False
    )


def test_on_the_viewers_own_suggestion_the_note_box_is_the_pitch():
    notes = [a_note(BO, "I'm in."), a_note(ADA, "Heeere's Johnny.")]

    assert film_card(a_suggestion(), notes, viewer=ADA).note_box == card.NoteBox(text="Heeere's Johnny.", is_pitch=True)
