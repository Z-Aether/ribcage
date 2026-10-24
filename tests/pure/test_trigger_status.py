"""A suggestion's DoesTheDogDie status: the four states derived from what is stored, the snapshot's text form, and the Films tab's words (#32, #102)."""

from datetime import UTC, datetime

import pytest

from ribcage.console.films import Row
from ribcage.films import card
from ribcage.suggestions.models import Approval
from ribcage.triggers.dtdd import NO_MATCH, Record, Snapshot, TopicCount
from ribcage.triggers.status import Fetched, State, Status, as_text, from_text, shown_counts
from tests.films import THE_SHINING

AT = datetime(2026, 10, 24, 18, 30, tzinfo=UTC)
SHINING = Record(12189, "The Shining", 1980, "Movie")
EMPTY = Record(1210242, "Werewolf By Night", 2022, "Movie")
COUNTED = Snapshot(SHINING, (TopicCount(153, 3, 1), TopicCount(200, 40, 2)))


def fetched(snapshot):
    return Fetched(snapshot, AT)


@pytest.mark.parametrize(
    "status, state",
    [
        (Status(has_tmdb_id=True, match=SHINING.item_id, fetched=fetched(COUNTED)), State.MATCHED),
        # Set by hand on a film added by hand, it is matched all the same.
        (Status(has_tmdb_id=False, match=SHINING.item_id, set_by="Iván", fetched=fetched(COUNTED)), State.MATCHED),
        # DoesTheDogDie answered with nothing: an empty record, or none at all.
        (Status(has_tmdb_id=True, match=EMPTY.item_id, fetched=fetched(Snapshot(EMPTY, ()))), State.UNCOVERED),
        (Status(has_tmdb_id=True, fetched=fetched(NO_MATCH)), State.UNCOVERED),
        # Something to look up, and no answer yet.
        (Status(has_tmdb_id=True), State.NOT_FETCHED),
        (Status(has_tmdb_id=False, match=SHINING.item_id, set_by="Iván"), State.NOT_FETCHED),
        (Status(has_tmdb_id=True, match=SHINING.item_id), State.NOT_FETCHED),
        # Added by hand, and nobody has pasted a link.
        (Status(has_tmdb_id=False), State.NO_MATCH),
    ],
)
def test_each_state_is_derived_from_the_match_and_the_snapshot(status, state):
    assert status.state is state


def test_not_fetched_never_reads_as_uncovered_or_clear():
    assert Status(has_tmdb_id=True).state not in {State.UNCOVERED, State.MATCHED}


@pytest.mark.parametrize("snapshot", [COUNTED, Snapshot(EMPTY, ()), NO_MATCH, Snapshot(Record(7, "Mārama", None, "TV Show"), ())])
def test_a_snapshot_reads_back_whole_from_its_text(snapshot):
    assert from_text(as_text(fetched(snapshot))) == fetched(snapshot)


def test_the_text_is_plain_json_holding_the_record_the_counts_and_when_it_was_fetched():
    assert as_text(fetched(COUNTED)) == (
        '{"record": {"item_id": 12189, "name": "The Shining", "release_year": 1980, "item_type": "Movie"}, '
        '"counts": [[153, 3, 1], [200, 40, 2]], "fetched_at": "2026-10-24T18:30:00+00:00"}'
    )


def test_only_the_named_topics_with_a_yes_vote_are_counted():
    status = Status(has_tmdb_id=True, match=SHINING.item_id, fetched=fetched(COUNTED))

    assert status.topics_shown_by({153, 158, 200}) == 2
    assert status.topics_shown_by({153}) == 1
    assert Status(has_tmdb_id=True).topics_shown_by({153}) == 0


def test_a_topic_with_no_yes_vote_is_not_counted_and_one_with_a_single_yes_is():
    counted = Snapshot(SHINING, (TopicCount(153, 0, 110), TopicCount(158, 1, 0), TopicCount(200, 0, 0)))
    status = Status(has_tmdb_id=True, match=SHINING.item_id, fetched=fetched(counted))

    assert status.topics_shown_by({153, 158, 200}) == 1
    assert shown_counts(counted.counts, {153, 158, 200}) == (TopicCount(158, 1, 0),)


def a_row(status, named=0):
    film_card = card.FilmCard(film=THE_SHINING, suggester="Ada", suggester_removed=False, pitch="A pitch.", notes=())
    return Row(film_card, Approval.UNDECIDED, dtdd=status, shown_topics=named)


@pytest.mark.parametrize(
    "status, named, words",
    [
        (Status(has_tmdb_id=True, match=SHINING.item_id, fetched=fetched(COUNTED)), 2, "2 topics"),
        (Status(has_tmdb_id=True, match=SHINING.item_id, fetched=fetched(COUNTED)), 1, "1 topic"),
        (Status(has_tmdb_id=True, fetched=fetched(NO_MATCH)), 0, "uncovered"),
        (Status(has_tmdb_id=True), 0, "not fetched"),
        (Status(has_tmdb_id=False), 0, "no match"),
    ],
)
def test_the_films_tab_names_each_state(status, named, words):
    assert a_row(status, named).dtdd_status == words
