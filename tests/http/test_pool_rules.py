"""The pool's database rules: what holds in every phase, whatever the app above it does (#26 §8)."""

import dataclasses
from contextlib import contextmanager

import pytest
from django.db import IntegrityError, transaction

from ribcage.films.film import RuntimeSource
from ribcage.identity.models import Voter
from ribcage.identity.removal import remove
from ribcage.suggestions.models import Approval, Note, Suggestion
from tests.films import CABINET_OF_CURIOSITIES, INFESTED, THE_SHINING

NO_RUNTIME = dataclasses.replace(THE_SHINING, runtime=None)


@pytest.fixture
def ada(db):
    return Voter.objects.create_voter("Ada")


@pytest.fixture
def bo(db):
    return Voter.objects.create_voter("Bo")


@contextmanager
def refused():
    # Atomic, so the refused write leaves the test's transaction usable.
    with pytest.raises(IntegrityError), transaction.atomic():
        yield


def test_a_suggestion_keeps_the_film_as_it_was_described_with_its_pitch_as_the_suggesters_note(ada):
    suggestion = Suggestion.objects.suggest(ada, INFESTED, "Spiders in a tower block.")

    stored = Suggestion.objects.get()
    assert stored.film == INFESTED
    assert (stored.runtime, stored.tmdb_runtime) == (106, 106)
    assert (stored.suggester, stored.suggester_name, stored.approval) == (ada, "Ada", Approval.UNDECIDED)
    assert list(stored.notes.values_list("author", "text")) == [(ada.pk, "Spiders in a tower block.")]
    assert stored == suggestion


def test_a_hand_entered_film_has_no_tmdb_runtime(ada):
    Suggestion.objects.suggest(ada, CABINET_OF_CURIOSITIES, "Just the one episode.")

    stored = Suggestion.objects.get()
    assert (stored.tmdb_id, stored.runtime, stored.tmdb_runtime) == (None, 47, None)
    assert stored.film == CABINET_OF_CURIOSITIES


def test_a_runtime_edited_at_the_step_is_stored_as_current_with_tmdbs_kept(ada):
    Suggestion.objects.suggest(ada, THE_SHINING, "Heeere's Johnny.", runtime=150)

    stored = Suggestion.objects.get()
    assert (stored.runtime, stored.tmdb_runtime) == (150, 144)
    assert stored.film == dataclasses.replace(THE_SHINING, runtime=150, runtime_source=RuntimeSource.HAND_ENTERED)


def test_a_second_suggestion_of_one_tmdb_id_is_refused(ada, bo):
    Suggestion.objects.suggest(ada, THE_SHINING, "Heeere's Johnny.")

    with refused():
        Suggestion.objects.suggest(bo, THE_SHINING, "Me too.")

    assert Suggestion.objects.count() == 1
    assert Note.objects.count() == 1


def test_two_hand_entered_films_with_one_title_are_both_kept(ada, bo):
    Suggestion.objects.suggest(ada, CABINET_OF_CURIOSITIES, "The Autopsy.")
    Suggestion.objects.suggest(bo, CABINET_OF_CURIOSITIES, "The Outside.")

    assert Suggestion.objects.filter(title=CABINET_OF_CURIOSITIES.title).count() == 2


def test_an_approved_suggestion_without_a_runtime_is_refused(ada):
    suggestion = Suggestion.objects.suggest(ada, NO_RUNTIME, "Heeere's Johnny.")

    with refused():
        Suggestion.objects.filter(pk=suggestion.pk).update(approval=Approval.APPROVED)

    assert Suggestion.objects.get().approval == Approval.UNDECIDED


def test_an_approved_suggestions_runtime_cannot_be_cleared(ada):
    suggestion = Suggestion.objects.suggest(ada, THE_SHINING, "Heeere's Johnny.")
    Suggestion.objects.filter(pk=suggestion.pk).update(approval=Approval.APPROVED)

    with refused():
        Suggestion.objects.filter(pk=suggestion.pk).update(runtime=None)

    assert Suggestion.objects.get().runtime == 144


@pytest.mark.parametrize("approval", [Approval.UNDECIDED, Approval.DROPPED])
def test_an_undecided_or_dropped_suggestion_may_have_no_runtime(ada, approval):
    suggestion = Suggestion.objects.suggest(ada, NO_RUNTIME, "Heeere's Johnny.")

    Suggestion.objects.filter(pk=suggestion.pk).update(approval=approval)

    assert Suggestion.objects.get().approval == approval


@pytest.mark.parametrize("field", ["runtime", "tmdb_runtime"])
@pytest.mark.parametrize("runtime", [0, -1])
def test_a_runtime_that_is_not_positive_is_refused(ada, field, runtime):
    suggestion = Suggestion.objects.suggest(ada, THE_SHINING, "Heeere's Johnny.")

    with refused():
        Suggestion.objects.filter(pk=suggestion.pk).update(**{field: runtime})

    assert getattr(Suggestion.objects.get(), field) == 144


def test_a_second_note_by_one_voter_on_one_film_is_refused(ada, bo):
    suggestion = Suggestion.objects.suggest(ada, THE_SHINING, "Heeere's Johnny.")
    suggestion.notes.create(author=bo, text="I'm in.")

    with refused():
        suggestion.notes.create(author=bo, text="Still in.")
    with refused():
        suggestion.notes.create(author=ada, text="A second pitch.")

    assert list(suggestion.notes.values_list("text", flat=True)) == ["Heeere's Johnny.", "I'm in."]


def test_one_voter_writes_a_note_on_each_of_many_films(ada, bo):
    for film in [THE_SHINING, INFESTED]:
        Suggestion.objects.suggest(ada, film, "Watch it.").notes.create(author=bo, text="I'm in.")

    assert bo.notes.count() == 2


def test_a_suggestion_deleted_takes_its_notes_with_it(ada, bo):
    suggestion = Suggestion.objects.suggest(ada, THE_SHINING, "Heeere's Johnny.")
    suggestion.notes.create(author=bo, text="I'm in.")

    suggestion.delete()

    assert not Note.objects.exists()


def test_a_removed_suggesters_link_goes_blank_and_their_name_and_pitch_stay(ada):
    Suggestion.objects.suggest(ada, THE_SHINING, "Heeere's Johnny.")

    remove(ada)

    suggestion = Suggestion.objects.get()
    assert (suggestion.suggester, suggestion.suggester_name) == (None, "Ada")
    assert list(suggestion.notes.values_list("author", "text")) == [(None, "Heeere's Johnny.")]
