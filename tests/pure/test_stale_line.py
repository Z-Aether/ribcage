"""The Films tab's stale line and the refresh's line: which films' trigger data is old or missing, and in what order a move refreshes them (#32 §1, #104)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from ribcage.console.films import ALL, Ledger, Row, chosen
from ribcage.films import card
from ribcage.suggestions.models import Approval
from ribcage.triggers.dtdd import Record, Snapshot, TopicCount
from ribcage.triggers.refresh import in_line
from ribcage.triggers.status import Fetched, Status
from tests.films import THE_SHINING

NOW = datetime(2026, 10, 24, 18, 30, tzinfo=UTC)
COUNTED = Snapshot(Record(1, "A film", 2000, "Movie"), (TopicCount(153, 3, 1),))


def fetched(days_ago):
    return Status(has_tmdb_id=True, match=1, fetched=Fetched(COUNTED, NOW - timedelta(days=days_ago)))


NOT_FETCHED = Status(has_tmdb_id=True)
BY_HAND = Status(has_tmdb_id=False)


def a_row(title, dtdd, approval=Approval.UNDECIDED):
    film_card = card.FilmCard(film=replace(THE_SHINING, title=title), suggester="Ada", suggester_removed=False, pitch="A pitch.", notes=())
    return Row(film_card, approval, dtdd=dtdd)


def line(*rows, show=ALL):
    return Ledger.of(list(rows), show, NOW).stale_line


def test_it_names_the_films_over_25_days_old_and_those_not_yet_fetched():
    shown = line(a_row("The Thing", fetched(27)), a_row("Weapons", NOT_FETCHED), a_row("Cube", fetched(26)), a_row("Pulse", fetched(3)))

    assert shown == "Trigger data is over 25 days old for The Thing and Cube, and not yet fetched for Weapons. They refresh on the next phase move."


@pytest.mark.parametrize(
    "rows, shown",
    [
        ([a_row("The Thing", fetched(27))], "Trigger data is over 25 days old for The Thing. It refreshes on the next phase move."),
        ([a_row("Weapons", NOT_FETCHED)], "Trigger data is not yet fetched for Weapons. It refreshes on the next phase move."),
        (
            [a_row("Weapons", NOT_FETCHED), a_row("Cube", NOT_FETCHED), a_row("Pulse", NOT_FETCHED)],
            "Trigger data is not yet fetched for Weapons, Cube and Pulse. They refresh on the next phase move.",
        ),
    ],
)
def test_it_words_one_film_or_several(rows, shown):
    assert line(*rows) == shown


def test_25_days_old_is_not_yet_stale():
    assert line(a_row("The Thing", fetched(25))) == ""


def test_it_shows_nothing_when_no_film_is_stale_or_unfetched():
    # A film added by hand has nothing to fetch, so it is never named.
    assert line(a_row("The Thing", fetched(3)), a_row("Cabinet of Curiosities", BY_HAND)) == ""


def test_it_names_every_film_whatever_the_filter():
    shown = line(a_row("Weapons", NOT_FETCHED, Approval.DROPPED), show=chosen("approved"))

    assert "Weapons" in shown


def test_the_line_runs_not_fetched_first_then_oldest_and_leaves_out_films_with_nothing_to_look_up():
    statuses = {1: fetched(3), 2: NOT_FETCHED, 3: fetched(27), 4: BY_HAND, 5: NOT_FETCHED, 6: fetched(10)}

    assert in_line(statuses) == [2, 5, 3, 6, 1]


def test_a_film_by_hand_with_a_match_is_in_line():
    assert in_line({1: Status(has_tmdb_id=False, match=7)}) == [1]
