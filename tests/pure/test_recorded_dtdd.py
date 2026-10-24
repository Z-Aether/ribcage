"""The seeded instance's DoesTheDogDie: the recordings answer the lookup by the client's own rule, and anything unrecorded reads as it not answering (#57, #102).

The recordings are gitignored, so these build theirs inline in a corpus of their own (#40, #56).
"""

import json
import shutil

import pytest

from ribcage.films import corpus
from ribcage.seeding.recorded import RecordedDtdd
from ribcage.triggers.client import Client, NotAnswering
from ribcage.triggers.dtdd import Record, Snapshot, TopicCount
from tests.dtdd import VOCABULARY, detail, item

WILLYS_WONDERLAND = 643586
WALLYS = item(191763, "Wally's Wonderland", 2021)
WILLYS = item(752870, "Willy's Wonderland", 2021)


@pytest.fixture
def directories(tmp_path):
    films, vocabulary = tmp_path / "films", tmp_path / "dtdd"
    films.mkdir()
    vocabulary.mkdir()
    shutil.copy(corpus.CORPUS_DIRECTORY / corpus.CORPUS_LIST, films)
    shutil.copytree(corpus.CORPUS_DIRECTORY / corpus.TMDB_RECORDINGS, films / corpus.TMDB_RECORDINGS)
    return films, vocabulary


def recorded(directories, vocabulary=True):
    films, vocabulary_directory = directories
    entry = next(entry for entry in corpus.read_entries(films) if entry.tmdb_id == WILLYS_WONDERLAND)
    recording = {"lookup": [WALLYS], "retry": [WILLYS], "items": {"191763": detail(WALLYS), "752870": detail(WILLYS, (153, 40, 0))}}
    (films / corpus.DTDD_RECORDINGS).mkdir()
    (films / corpus.DTDD_RECORDINGS / f"{entry.recording_name}.json").write_text(json.dumps(recording), encoding="utf-8")
    if vocabulary:
        for path, name in corpus.VOCABULARY_FILES.items():
            (vocabulary_directory / name).write_text(json.dumps(VOCABULARY[path]), encoding="utf-8")
    return RecordedDtdd(films, vocabulary_directory)


def test_a_lookup_is_answered_from_its_recording_retry_included(directories):
    snapshot = Client("key", recorded(directories)).lookup(WILLYS_WONDERLAND, "Willy's Wonderland", 2021).value

    assert snapshot == Snapshot(Record(752870, "Willy's Wonderland", 2021, "Movie"), (TopicCount(153, 40, 0),))


def test_the_vocabulary_is_answered_from_its_recording(directories):
    vocabulary = Client("key", recorded(directories)).vocabulary().value

    assert [topic.label for topic in vocabulary.topics] == ["dog death", "cat death", "jump scares"]


def test_the_recordings_say_whether_they_are_there(directories):
    assert not RecordedDtdd(*directories).is_recorded
    assert recorded(directories).is_recorded


def test_without_a_vocabulary_they_are_not_recorded_and_it_is_not_answering(directories):
    recordings = recorded(directories, vocabulary=False)

    assert not recordings.is_recorded
    with pytest.raises(NotAnswering):
        Client("key", recordings).vocabulary()


@pytest.mark.parametrize(
    "ask",
    [
        lambda client: client.lookup(694, "The Shining", 1980),
        lambda client: client.record(12243),
    ],
)
def test_anything_unrecorded_reads_as_dtdd_not_answering(directories, ask):
    with pytest.raises(NotAnswering):
        ask(Client("key", recorded(directories)))

