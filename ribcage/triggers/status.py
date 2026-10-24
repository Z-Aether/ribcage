"""A suggestion's DoesTheDogDie data as stored, the snapshot's text form, and the four states they make (#32, #102)."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from ribcage.triggers.dtdd import Record, Snapshot, TopicCount


# Named on the Films tab ahead of DoesTheDogDie's 30-day cache limit, so a move or two can still refresh it (#5, #32 §1, #104).
STALE_AFTER = timedelta(days=25)


class State(StrEnum):
    """Derived and never stored, so no field can disagree with the data it names (#26, #32)."""

    MATCHED = "matched"
    UNCOVERED = "uncovered"
    NOT_FETCHED = "not fetched"
    NO_MATCH = "no match"


@dataclass(frozen=True)
class Fetched:
    """A snapshot with the time it was fetched, read and written whole (#32 §1)."""

    snapshot: Snapshot
    fetched_at: datetime


@dataclass(frozen=True)
class Status:
    """A suggestion's match, who set it, and its snapshot, if DoesTheDogDie has answered for it."""

    has_tmdb_id: bool
    match: int | None = None
    # Empty for `auto`; else the setter's kept display name, so it outlives their removal (#105).
    set_by: str = ""
    fetched: Fetched | None = None

    @property
    def state(self):
        if self.fetched is not None:
            return State.UNCOVERED if self.fetched.snapshot.is_uncovered else State.MATCHED
        # Something to look up but no answer yet: never an all-clear, never uncovered (#32 §2).
        if self.has_tmdb_id or self.match is not None:
            return State.NOT_FETCHED
        # Added by hand with no match: nothing is looked up until someone pastes a link (#105).
        return State.NO_MATCH

    def is_stale(self, now):
        return self.fetched is not None and now - self.fetched.fetched_at > STALE_AFTER

    def topics_named_by(self, topic_ids):
        """How many of the snapshot's topics the vocabulary names; the rest stay off every surface until it does (#62)."""
        if self.fetched is None:
            return 0
        return sum(count.topic_id in topic_ids for count in self.fetched.snapshot.counts)


def as_text(fetched):
    """The stored form: JSON text, since a JSONField's system check opens the database and backupcode must not (#68)."""
    snapshot, record = fetched.snapshot, fetched.snapshot.record
    return json.dumps(
        {
            "record": None
            if record is None
            else {"item_id": record.item_id, "name": record.name, "release_year": record.release_year, "item_type": record.item_type},
            "counts": [[count.topic_id, count.yes, count.no] for count in snapshot.counts],
            "fetched_at": fetched.fetched_at.isoformat(),
        },
        ensure_ascii=False,
    )


def from_text(text):
    stored = json.loads(text)
    record = None if stored["record"] is None else Record(**stored["record"])
    counts = tuple(TopicCount(topic_id, yes, no) for topic_id, yes, no in stored["counts"])
    return Fetched(Snapshot(record, counts), datetime.fromisoformat(stored["fetched_at"]))
