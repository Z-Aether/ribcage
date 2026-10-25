import json
import shutil
import socket
from datetime import timedelta
from io import BytesIO, StringIO, TextIOWrapper

import pytest
from django.contrib.auth import authenticate
from django.core.management import CommandError, call_command
from django.utils import timezone

from ribcage.films import corpus
from ribcage.identity.models import Voter
from ribcage.phase.history import current
from ribcage.phase.models import PhaseMove
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.phase import history
from ribcage.seeding.recorded import RecordedDtdd
from ribcage.triggers import client as dtdd_client
from ribcage.triggers import refresh, stored
from ribcage.triggers.models import Topic, TriggerData
from ribcage.triggers.status import State
from tests.dtdd import VOCABULARY, detail, item

SEEDED_DISPLAY_NAMES = ["Ada", "Anne-Marie", "O'Brien", "Zoë", "Sam", "Bartholomew Winthrop"]
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


def test_with_no_phase_named_it_seeds_a_fresh_suggest_with_no_history(transactional_db, debug_on):
    call_command("seed")

    assert current() is Phase.SUGGEST
    assert not PhaseMove.objects.exists()


def test_the_output_names_the_seeded_phase(transactional_db, debug_on):
    output = StringIO()

    call_command("seed", "--phase", "PICK", stdout=output)

    assert "Seeded PICK" in output.getvalue()


def seeded_state():
    return [(voter.pk, voter.display_name) for voter in Voter.objects.order_by("pk")]


def test_seeding_starts_from_nothing(transactional_db, debug_on):
    Voter.objects.create_voter("Interloper")

    call_command("seed")

    assert [display_name for _, display_name in seeded_state()] == SEEDED_DISPLAY_NAMES


def test_seeding_twice_gives_the_same_state(transactional_db, debug_on):
    call_command("seed")
    first = seeded_state()

    call_command("seed")

    assert seeded_state() == first


def test_the_output_names_every_seeded_voter_and_the_password(transactional_db, debug_on):
    output = StringIO()

    call_command("seed", stdout=output)

    assert all(display_name in output.getvalue() for display_name in SEEDED_DISPLAY_NAMES)
    assert SEEDED_PASSWORD in output.getvalue()


def test_the_voter_list_reaches_a_redirected_cp1252_stdout_as_utf8(transactional_db, debug_on):
    redirected = TextIOWrapper(BytesIO(), encoding="cp1252")

    call_command("seed", stdout=redirected)

    redirected.flush()
    assert "Zoë" in redirected.buffer.getvalue().decode("utf-8")


CABINET_OF_CURIOSITIES = "Del Toro's Cabinet of Curiosities"


def test_a_seeded_suggest_has_every_suggestion_undecided(transactional_db, debug_on):
    call_command("seed")

    assert set(Suggestion.objects.values_list("approval", flat=True)) == {Approval.UNDECIDED}


def test_the_pool_is_seeded_offline(transactional_db, debug_on, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("seed went online")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)

    call_command("seed", "--phase", "APPROVE")

    assert Suggestion.objects.exists()


def seeded_pool():
    return list(Suggestion.objects.order_by("pk").values_list("pk", "title", "suggester_name", "approval"))


def test_seeding_twice_gives_the_same_pool(transactional_db, debug_on):
    call_command("seed", "--phase", "APPROVE")
    first = seeded_pool()

    call_command("seed", "--phase", "APPROVE")

    assert seeded_pool() == first


# Trigger data (#102)

THE_THING, WEREWOLF_BY_NIGHT, WEAPONS, EXIT_8 = 1091, 894205, 1078605, 1408208


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
    return films, vocabulary


def seeded_states():
    suggestions = list(Suggestion.objects.all())
    statuses = stored.statuses_of(suggestions)
    return {suggestion.tmdb_id or suggestion.title: statuses[suggestion.pk].state for suggestion in suggestions}


def test_without_the_recordings_seed_runs_leaving_every_film_not_fetched_and_says_so(transactional_db, debug_on, corpus_without_dtdd):
    output = StringIO()

    call_command("seed", stdout=output)

    states = seeded_states()
    assert states.pop(CABINET_OF_CURIOSITIES) is State.NO_MATCH
    assert set(states.values()) == {State.NOT_FETCHED}
    assert not Topic.objects.exists()
    assert "DoesTheDogDie's recordings are missing, so every film is left not fetched and the vocabulary empty." in output.getvalue()
    assert "python manage.py fetchcorpus" in output.getvalue()


def record(directory, tmdb_id, recording):
    entry = next(entry for entry in corpus.read_entries(directory) if entry.tmdb_id == tmdb_id)
    (directory / corpus.DTDD_RECORDINGS).mkdir(exist_ok=True)
    (directory / corpus.DTDD_RECORDINGS / f"{entry.recording_name}.json").write_text(json.dumps(recording), encoding="utf-8")


def record_three(films, vocabulary):
    for path, name in corpus.VOCABULARY_FILES.items():
        (vocabulary / name).write_text(json.dumps(VOCABULARY[path]), encoding="utf-8")
    thing, werewolf, weapons = item(12243, "The Thing", 1982), item(1210242, "Werewolf By Night", 2022), item(1, "Weapons", 2025)
    record(films, THE_THING, {"lookup": [thing], "retry": None, "items": {"12243": detail(thing, (153, 3, 1))}})
    # Its real record has no year, so the retry by title rejects it and the film is uncovered on the empty one (#62).
    werewolf_real = {**item(834224, "Werewolf by Night", None), "topicItemStats": []}
    werewolf_items = {"1210242": detail(werewolf), "834224": detail(werewolf_real, (153, 9, 0))}
    record(films, WEREWOLF_BY_NIGHT, {"lookup": [werewolf], "retry": [werewolf_real], "items": werewolf_items})
    record(films, WEAPONS, {"lookup": [weapons], "retry": None, "items": {"1": detail(weapons, (200, 4, 0))}})


def test_seed_fills_the_vocabulary_and_each_recorded_films_snapshot_by_the_lookup_rule(transactional_db, debug_on, corpus_without_dtdd):
    record_three(*corpus_without_dtdd)
    output = StringIO()

    call_command("seed", stdout=output)

    states = seeded_states()
    assert (states[THE_THING], states[WEREWOLF_BY_NIGHT], states[WEAPONS], states[CABINET_OF_CURIOSITIES]) == (
        State.MATCHED,
        State.UNCOVERED,
        State.NOT_FETCHED,
        State.NO_MATCH,
    )
    assert Topic.objects.count() == len(VOCABULARY["/topics"])
    assert "DoesTheDogDie: 1 matched, 1 uncovered, 17 not fetched, 1 no match." in output.getvalue()
    assert "recordings are missing" not in output.getvalue()
    # The Thing's snapshot is 27 days old, so the Films tab's stale line names it (#104).
    statuses = stored.statuses_of(list(Suggestion.objects.all()))
    ages = {each.tmdb_id: timezone.now() - statuses[each.pk].fetched.fetched_at for each in Suggestion.objects.all() if statuses[each.pk].fetched}
    assert timedelta(days=27) <= ages.pop(THE_THING) < timedelta(days=27, minutes=5)
    assert all(age < timedelta(minutes=5) for age in ages.values())


def test_seed_matches_exit_8_auto_to_its_empty_duplicate_for_correcting(transactional_db, debug_on, corpus_without_dtdd):
    # Its id lookup returns both, and the rule rightly takes the voted one, so the seed sets the wrong one on purpose (#57, #105).
    films, vocabulary = corpus_without_dtdd
    record_three(films, vocabulary)
    real, duplicate = item(1558416, "Exit 8", 2025), item(1362774, "８番出口", 2025)
    record(films, EXIT_8, {"lookup": [real, duplicate], "retry": None, "items": {"1558416": detail(real, (153, 3, 1)), "1362774": detail(duplicate)}})

    call_command("seed", stdout=StringIO())

    exit_8 = Suggestion.objects.get(tmdb_id=EXIT_8)
    status = stored.statuses_of([exit_8])[exit_8.pk]
    assert (status.match, status.set_by, status.state) == (1362774, "", State.UNCOVERED)
    assert status.fetched.snapshot.record.name == "８番出口"


def test_without_its_recording_exit_8_stays_as_looked_up(transactional_db, debug_on, corpus_without_dtdd):
    record_three(*corpus_without_dtdd)

    call_command("seed", stdout=StringIO())

    assert seeded_states()[EXIT_8] is State.NOT_FETCHED


def test_a_phase_move_on_the_seeded_instance_refreshes_from_the_recordings(transactional_db, debug_on, corpus_without_dtdd, monkeypatch):
    record_three(*corpus_without_dtdd)
    call_command("seed", stdout=StringIO())
    monkeypatch.setattr(dtdd_client, "stand_in", None)
    # As seededserver does before serving (#102).
    dtdd_client.answer_from(RecordedDtdd())

    history.move(Phase.SUGGEST, Phase.APPROVE)
    refresh.after_the_move()

    states = seeded_states()
    assert (states[THE_THING], states[WEAPONS]) == (State.MATCHED, State.MATCHED)
    thing = Suggestion.objects.get(tmdb_id=THE_THING)
    assert timezone.now() - stored.statuses_of([thing])[thing.pk].fetched.fetched_at < timedelta(minutes=5)


def test_seed_in_run_leaves_the_matches_and_no_snapshot_or_vocabulary_as_the_purge_does(transactional_db, debug_on, corpus_without_dtdd):
    record_three(*corpus_without_dtdd)
    output = StringIO()

    call_command("seed", "--phase", "RUN", stdout=output)

    thing = Suggestion.objects.get(tmdb_id=THE_THING)
    assert TriggerData.objects.get(suggestion=thing).match == 12243
    assert not TriggerData.objects.filter(snapshot__isnull=False).exists()
    assert not Topic.objects.exists()
    assert set(seeded_states().values()) <= {State.NOT_FETCHED, State.NO_MATCH}
    assert "no snapshots or vocabulary" in output.getvalue()


def test_seed_ticks_the_watched_lists_by_label_and_leaves_sam_with_none(transactional_db, debug_on, corpus_without_dtdd, monkeypatch):
    from ribcage.seeding import watched as seeded_watched
    from ribcage.triggers.models import WatchedTopic

    record_three(*corpus_without_dtdd)
    monkeypatch.setattr(seeded_watched, "SEEDED_WATCHED_LISTS", {"Ada": ["dog death", "jump scares", "unheard of"], "Zoë": ["cat death"]})

    call_command("seed", stdout=StringIO())

    lists = {voter.display_name: sorted(voter.watched_topics.values_list("topic_id", flat=True)) for voter in Voter.objects.all()}
    assert lists["Ada"] == [153, 200] and lists["Zoë"] == [158] and lists["Sam"] == []
    assert WatchedTopic.objects.count() == 3


def test_seed_in_run_keeps_the_watched_lists_the_purge_leaves(transactional_db, debug_on, corpus_without_dtdd, monkeypatch):
    from ribcage.seeding import watched as seeded_watched

    record_three(*corpus_without_dtdd)
    monkeypatch.setattr(seeded_watched, "SEEDED_WATCHED_LISTS", {"Ada": ["dog death"]})

    call_command("seed", "--phase", "RUN", stdout=StringIO())

    assert list(Voter.objects.get(display_name="Ada").watched_topics.values_list("topic_id", flat=True)) == [153]
    assert not Topic.objects.exists()
