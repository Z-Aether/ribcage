"""DoesTheDogDie's records read into plain data, and the lookup's rules over them (#19, #20, #101)."""

import re
from dataclasses import dataclass

# TMDB's movie and TV ids collide in DoesTheDogDie's one tmdbId column, so the automatic lookup keeps movies alone (#19).
MOVIE = "Movie"


@dataclass(frozen=True)
class Record:
    """One DoesTheDogDie item, of any item type: a series added by hand is a "TV Show" there (#19)."""

    item_id: int
    name: str
    release_year: int | None
    item_type: str


@dataclass(frozen=True)
class TopicCount:
    topic_id: int
    yes: int
    no: int


@dataclass(frozen=True)
class Snapshot:
    """The record a film is matched to, None if there is none, and its counts for every topic with a vote (#19, #32)."""

    record: Record | None
    counts: tuple[TopicCount, ...]

    @property
    def is_uncovered(self):
        return not self.counts


NO_MATCH = Snapshot(None, ())


def normalised(title):
    return re.sub(r"[^0-9a-z]", "", title.casefold())


def an_int(value):
    if type(value) is not int:
        raise ValueError(f"{value!r} is not a whole number.")
    return value


def an_int_or_none(value):
    return None if value is None else an_int(value)


def a_string(value):
    if not isinstance(value, str):
        raise ValueError(f"{value!r} is not a string.")
    return value


def record_from(listed):
    return Record(
        item_id=an_int(listed["id"]),
        name=a_string(listed["name"]),
        release_year=an_int_or_none(listed.get("releaseYear")),
        item_type=a_string(listed["itemTypeName"]),
    )


def records_from(answer):
    """`/items`, by TMDB id or by title: an array of records."""
    if not isinstance(answer, list):
        raise ValueError("/items answers an array.")
    return [record_from(listed) for listed in answer]


def snapshot_from(detail):
    """`/items/<id>`: the record with its `topicItemStats`, where DoesTheDogDie omits a topic without votes (#19)."""
    stats = detail["topicItemStats"]
    if not isinstance(stats, list):
        raise ValueError("topicItemStats is an array.")
    counts = (TopicCount(an_int(stat["topicId"]), an_int(stat["yesSum"]), an_int(stat["noSum"])) for stat in stats)
    return Snapshot(record_from(detail), tuple(count for count in counts if count.yes or count.no))


def most_voted(snapshots):
    # The first of equals wins, so an empty duplicate never beats the record it duplicates (#57).
    return max(snapshots, key=lambda snapshot: len(snapshot.counts), default=None)


def accepted_on_retry(record, title, year):
    # The name exact once normalised and the year exact, as #20 §7 says; a yearless side agrees with nothing (#62).
    return year is not None and record.release_year == year and normalised(record.name) == normalised(title)
