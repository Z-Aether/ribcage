import shutil
import socket
from io import StringIO

import pytest
from django.contrib.auth import authenticate
from django.core.management import CommandError, call_command

from ribcage.films import corpus
from ribcage.identity.models import Voter
from ribcage.suggestions.models import Suggestion

SEEDED_PASSWORD = "popcorn-before-midnight"

pytestmark = pytest.mark.usefixtures("fast_hashing")


def test_with_debug_off_it_refuses_and_leaves_the_database_alone(transactional_db, settings):
    settings.DEBUG = False
    Voter.objects.create_voter("Before the seed")

    with pytest.raises(CommandError, match="only with DEBUG on"):
        call_command("seed")

    assert list(Voter.objects.values_list("display_name", flat=True)) == ["Before the seed"]
    assert authenticate(display_name="Ada", password=SEEDED_PASSWORD) is None


@pytest.mark.parametrize("phase", ["SETUP", "vote", "Suggest", "", "SOLVE"])
def test_anything_but_the_five_phases_is_refused_and_the_database_left_alone(transactional_db, debug_on, phase):
    Voter.objects.create_voter("Before the seed")

    with pytest.raises(CommandError, match="invalid choice"):
        call_command("seed", "--phase", phase)

    assert list(Voter.objects.values_list("display_name", flat=True)) == ["Before the seed"]


def seeded_state():
    voters = list(Voter.objects.order_by("pk").values_list("pk", "display_name"))
    pool = list(Suggestion.objects.order_by("pk").values_list("pk", "title", "suggester_name", "approval"))
    return voters, pool


def test_seeding_twice_gives_the_same_state(transactional_db, debug_on):
    call_command("seed", "--phase", "APPROVE")
    first = seeded_state()

    call_command("seed", "--phase", "APPROVE")

    assert seeded_state() == first


def test_the_pool_is_seeded_offline(transactional_db, debug_on, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("seed went online")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)

    call_command("seed", "--phase", "APPROVE")

    assert Suggestion.objects.exists()


@pytest.fixture
def corpus_without_dtdd(tmp_path, monkeypatch):
    """The corpus as a fresh clone has it: the committed files only, with no DoesTheDogDie recordings or vocabulary (#40)."""
    films, vocabulary = tmp_path / "films", tmp_path / "dtdd"
    films.mkdir()
    vocabulary.mkdir()
    shutil.copy(corpus.CORPUS_DIRECTORY / corpus.CORPUS_LIST, films)
    shutil.copytree(corpus.CORPUS_DIRECTORY / corpus.TMDB_RECORDINGS, films / corpus.TMDB_RECORDINGS)
    monkeypatch.setattr(corpus, "CORPUS_DIRECTORY", films)
    monkeypatch.setattr(corpus, "VOCABULARY_DIRECTORY", vocabulary)


def test_without_the_recordings_seed_still_runs(transactional_db, debug_on, corpus_without_dtdd):
    call_command("seed", stdout=StringIO())

    assert Suggestion.objects.exists()
