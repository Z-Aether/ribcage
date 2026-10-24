import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ribcage.films import tmdb
from ribcage.films.film import Film, hand_entered

CORPUS_DIRECTORY = Path(__file__).resolve().parents[2] / "fixtures" / "films"
CORPUS_LIST = "corpus.json"
TMDB_RECORDINGS = "tmdb"
# Gitignored under DoesTheDogDie's redistribution terms, so a fresh clone has none (#40).
DTDD_RECORDINGS = "dtdd"
# DoesTheDogDie's vocabulary as last recorded, gitignored under the same terms (#40, #101).
VOCABULARY_DIRECTORY = CORPUS_DIRECTORY.parent / "dtdd"
VOCABULARY_FILES = {
    "/topics": "dtdd_topics.json",
    "/topiccategories": "dtdd_topiccategories.json",
    "/topicsupercategories": "dtdd_topicsupercategories.json",
}
FETCH_COMMAND = "python manage.py fetchcorpus"


@dataclass(frozen=True)
class CorpusEntry:
    """One film of the seed corpus as the group wrote it, and the TMDB film a person picked for it (#5, #25)."""

    written_title: str
    written_year: int | None
    tmdb_id: int | None
    # Only a hand-entered entry, one with no TMDB id, carries its own runtime.
    runtime: int | None = None

    @property
    def is_hand_entered(self):
        return self.tmdb_id is None

    @property
    def recording_name(self):
        ascii_title = unicodedata.normalize("NFKD", self.written_title).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
        return f"{slug}-{self.written_year}" if self.written_year else slug

    def __str__(self):
        return f"{self.written_title} ({self.written_year})" if self.written_year else self.written_title


@dataclass(frozen=True)
class RecordedFilm:
    entry: CorpusEntry
    film: Film
    # What a search for the title as written returned: the picker's input, where the ranking traps live (#25).
    search_results: tuple[tmdb.SearchResult, ...]
    dtdd_recorded: bool


class DtddNotRecorded(LookupError):
    pass


def read_entries(directory=CORPUS_DIRECTORY):
    entries = json.loads((Path(directory) / CORPUS_LIST).read_text(encoding="utf-8"))
    return [CorpusEntry(**entry) for entry in entries]


def read_corpus(directory=CORPUS_DIRECTORY):
    directory = Path(directory)
    return [read_film(entry, directory) for entry in read_entries(directory)]


def read_tmdb(entry, directory=CORPUS_DIRECTORY):
    """The raw TMDB recording for one entry: the search by its written title, and the detail of its film, None if hand-entered."""
    return json.loads((Path(directory) / TMDB_RECORDINGS / f"{entry.recording_name}.json").read_text(encoding="utf-8"))


def read_film(entry, directory):
    recording = read_tmdb(entry, directory)
    if entry.is_hand_entered:
        film = hand_entered(entry.written_title, entry.written_year, entry.runtime)
    else:
        film = tmdb.film_from_detail(recording["detail"])
    return RecordedFilm(
        entry=entry,
        film=film,
        search_results=tmdb.search_results(recording["search"]),
        dtdd_recorded=dtdd_path(entry, directory).is_file(),
    )


def read_dtdd(entry, directory=CORPUS_DIRECTORY):
    """The raw DoesTheDogDie recording for one entry: the lookup by TMDB id, any retry by title, and the items."""
    if entry.is_hand_entered:
        # A hand-entered film has no match until someone pastes a link, so nothing is looked up (#32).
        raise DtddNotRecorded(f"{entry} is hand-entered, so nothing was looked up on DoesTheDogDie.")
    path = dtdd_path(entry, Path(directory))
    if not path.is_file():
        raise DtddNotRecorded(
            f"No DoesTheDogDie payload is recorded for {entry}. They are gitignored under DTDD's terms, "
            f"so a fresh clone has none: run {FETCH_COMMAND} with the keys set to record them."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def read_vocabulary(directory=VOCABULARY_DIRECTORY):
    """DoesTheDogDie's three vocabulary lists as recorded, raw, keyed by the path each answers (#23, #101)."""
    paths = {path: Path(directory) / name for path, name in VOCABULARY_FILES.items()}
    if not all(path.is_file() for path in paths.values()):
        raise DtddNotRecorded(
            f"DoesTheDogDie's vocabulary isn't recorded in {directory}. It is gitignored under DTDD's terms, "
            f"so a fresh clone has none: run {FETCH_COMMAND} --vocabulary with the keys set to record it."
        )
    return {path: json.loads(file.read_text(encoding="utf-8")) for path, file in paths.items()}


def dtdd_path(entry, directory):
    return directory / DTDD_RECORDINGS / f"{entry.recording_name}.json"
