"""Every phase move's DoesTheDogDie refresh, after the move commits, and the Films tab's stale line (#32 §1, #104)."""

import re
import urllib.error
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from ribcage.console.moves import make
from ribcage.phase.history import current
from ribcage.phase.models import PhaseMove
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Suggestion
from ribcage.triggers import client as dtdd_client
from ribcage.triggers import refresh, stored
from ribcage.triggers.dtdd import Record, Snapshot, TopicCount
from ribcage.triggers.models import Topic, TriggerData
from ribcage.triggers.status import State
from tests.dtdd import VOCABULARY, VOCABULARY_PATHS, Dtdd, detail, item
from tests.films import CABINET_OF_CURIOSITIES, a_tmdb_film
from tests.http.signing_in import sign_in_as_the_admin
from tests.http.test_phase import walk_to

TAB = "/console/films/"
MOVE = "/console/phase/move/"
THING, CUBE, PULSE, WEAPONS = item(11, "The Thing", 1982), item(12, "Cube", 1997), item(13, "Pulse", 2001), item(14, "Weapons", 2025)


class Clock:
    """A monotonic clock the transport advances, so the refresh's 20 s pass in no time."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def snapshot_of(listed, *counts):
    return Snapshot(Record(listed["id"], listed["name"], listed["releaseYear"], "Movie"), tuple(TopicCount(*count) for count in counts))


def fetched_days_ago(suggestion, listed, days, *counts, set_by=""):
    stored.store_lookup(suggestion, snapshot_of(listed, *counts), timezone.now() - timedelta(days=days))
    if set_by:
        TriggerData.objects.filter(suggestion=suggestion).update(match_set_by=set_by)


def status_of(suggestion):
    return stored.statuses_of([suggestion])[suggestion.pk]


def fetched_at(suggestion):
    return status_of(suggestion).fetched.fetched_at


@pytest.fixture
def pool(voters):
    """Oldest suggestion first: Weapons not fetched, The Thing 27 days old, Cube 26, Pulse 3, and a film by hand."""
    ada = voters["ada"]
    films = {
        "thing": Suggestion.objects.suggest(ada, a_tmdb_film(1091, "The Thing"), "Pitch."),
        "cube": Suggestion.objects.suggest(ada, a_tmdb_film(431, "Cube"), "Pitch."),
        "pulse": Suggestion.objects.suggest(ada, a_tmdb_film(19185, "Pulse"), "Pitch."),
        "weapons": Suggestion.objects.suggest(ada, a_tmdb_film(1078605, "Weapons"), "Pitch."),
        "cabinet": Suggestion.objects.suggest(ada, CABINET_OF_CURIOSITIES, "Pitch."),
    }
    fetched_days_ago(films["thing"], THING, 27, (153, 1, 0))
    fetched_days_ago(films["cube"], CUBE, 26, (153, 1, 0))
    fetched_days_ago(films["pulse"], PULSE, 3, (153, 1, 0))
    return films


def answering(**options):
    """DoesTheDogDie with fresh counts for every film: Weapons found by its TMDB id, the rest by their match."""
    details = [detail(THING, (153, 5, 0)), detail(CUBE, (200, 2, 0)), detail(PULSE, (158, 1, 1)), detail(WEAPONS, (200, 4, 0))]
    return Dtdd(by_tmdb={1078605: [WEAPONS]}, details=details, **options)


def refreshed(transport, clock=None):
    refresh.refresh(dtdd_client.Client("key", transport), clock or Clock())


def test_the_vocabulary_refreshes_first_and_is_replaced_whole(pool):
    stored.replace_vocabulary(dtdd_client.Client("key", Dtdd(vocabulary={**VOCABULARY, "/topics": VOCABULARY["/topics"][:1]})).vocabulary().value)
    transport = answering()

    refreshed(transport)

    assert transport.paths[:3] == VOCABULARY_PATHS
    assert Topic.objects.count() == len(VOCABULARY["/topics"])


def test_not_fetched_films_go_first_then_the_oldest_and_a_film_by_hand_is_skipped(pool):
    transport = answering()

    refreshed(transport)

    # Weapons has no match, so it runs the whole lookup; each matched film costs its one call.
    assert transport.paths[3:] == ["/items", "/items/14", "/items/11", "/items/12", "/items/13"]
    assert status_of(pool["weapons"]).state is State.MATCHED
    assert status_of(pool["thing"]).fetched.snapshot.counts == (TopicCount(153, 5, 0),)
    assert all(fetched_at(pool[film]) > timezone.now() - timedelta(minutes=1) for film in ["thing", "cube", "pulse", "weapons"])
    assert status_of(pool["cabinet"]).state is State.NO_MATCH


def test_every_approval_is_refreshed(pool):
    Suggestion.objects.filter(pk=pool["thing"].pk).update(approval="dropped")
    transport = answering()

    refreshed(transport)

    assert "/items/11" in transport.paths


def test_a_matched_film_costs_one_call_and_keeps_its_match_and_setter(pool):
    Suggestion.objects.exclude(pk=pool["thing"].pk).delete()
    TriggerData.objects.filter(suggestion=pool["thing"]).update(match_set_by="Iván")
    transport = answering()

    refreshed(transport)

    assert transport.paths == [*VOCABULARY_PATHS, "/items/11"]
    status = status_of(pool["thing"])
    assert (status.match, status.set_by, status.fetched.snapshot.counts) == (11, "Iván", (TopicCount(153, 5, 0),))


def test_an_uncovered_film_with_no_match_runs_the_whole_lookup(voters):
    pulse = Suggestion.objects.suggest(voters["ada"], a_tmdb_film(19185, "Pulse"), "Pitch.")
    stored.store_lookup(pulse, Snapshot(None, ()), timezone.now() - timedelta(days=3))
    transport = Dtdd(by_tmdb={19185: [PULSE]}, details=[detail(PULSE, (158, 1, 1))])

    refreshed(transport)

    assert transport.paths == [*VOCABULARY_PATHS, "/items", "/items/13"]
    assert (status_of(pulse).state, status_of(pulse).match) == (State.MATCHED, 13)


def test_it_stops_once_dtdd_has_3_calls_left_this_minute(pool):
    # The vocabulary's three calls leave 7, 6 and 5; Weapons' lookup leaves 4 and then 3, and nothing more is asked.
    transport = answering(remaining=[7, 6, 5, 4, 3, 2])

    refreshed(transport)

    assert transport.paths == [*VOCABULARY_PATHS, "/items", "/items/14"]
    assert status_of(pool["weapons"]).state is State.MATCHED
    assert fetched_at(pool["thing"]) < timezone.now() - timedelta(days=26)


def test_a_film_with_no_match_stopped_at_the_floor_partway_keeps_its_state(pool):
    transport = answering(remaining=[6, 5, 4, 3])

    refreshed(transport)

    assert transport.paths == [*VOCABULARY_PATHS, "/items"]
    assert status_of(pool["weapons"]).state is State.NOT_FETCHED


def test_it_stops_at_20_seconds(pool):
    clock = Clock()

    def eight_seconds_a_film(path):
        if path.startswith("/items/"):
            clock.now += 8

    transport = answering(on_call=eight_seconds_a_film)

    refreshed(transport, clock)

    # Weapons' detail ends at 8 s and The Thing's at 16 s, so Cube's starts inside the 20 s and Pulse's, at 24 s, is never made.
    assert transport.paths[3:] == ["/items", "/items/14", "/items/11", "/items/12"]
    assert fetched_at(pool["pulse"]) < timezone.now() - timedelta(days=2)


FAILURES = [
    TimeoutError(),
    urllib.error.HTTPError("https://www.doesthedogdie.com/api/v3/items/11", 503, "Service Unavailable", {}, None),
    urllib.error.HTTPError("https://www.doesthedogdie.com/api/v3/items/11", 429, "Too Many Requests", {}, None),
]


@pytest.mark.parametrize("failure", FAILURES)
def test_the_first_failure_ends_the_batch_and_keeps_the_old_snapshots(pool, failure):
    def failing_on_the_thing(path):
        if path == "/items/11":
            raise failure

    before = {film: status_of(pool[film]).fetched for film in ["thing", "cube", "pulse"]}
    transport = answering(on_call=failing_on_the_thing)

    refreshed(transport)

    assert transport.paths[3:] == ["/items", "/items/14", "/items/11"]
    assert {film: status_of(pool[film]).fetched for film in ["thing", "cube", "pulse"]} == before
    assert status_of(pool["weapons"]).state is State.MATCHED


def test_a_record_gone_from_dtdd_is_skipped_and_the_refresh_carries_on(pool):
    # The Thing's record answers 404, as one deleted on DoesTheDogDie does; Cube and Pulse behind it still refresh (#104).
    details = [detail(CUBE, (200, 2, 0)), detail(PULSE, (158, 1, 1)), detail(WEAPONS, (200, 4, 0))]
    before = status_of(pool["thing"])
    transport = Dtdd(by_tmdb={1078605: [WEAPONS]}, details=details)

    refreshed(transport)

    assert transport.paths[3:] == ["/items", "/items/14", "/items/11", "/items/12", "/items/13"]
    assert (status_of(pool["thing"]).match, status_of(pool["thing"]).fetched) == (before.match, before.fetched)
    assert status_of(pool["cube"]).fetched.snapshot.counts == (TopicCount(200, 2, 0),)
    assert status_of(pool["pulse"]).fetched.snapshot.counts == (TopicCount(158, 1, 1),)


def test_a_record_gone_near_the_floor_counts_against_it(pool):
    # Weapons' lookup leaves 17 and 16; The Thing's 404 says 3 are left, so Cube is not asked (#104).
    details = [detail(WEAPONS, (200, 4, 0))]
    transport = Dtdd(by_tmdb={1078605: [WEAPONS]}, details=details, remaining=[20, 19, 18, 17, 16, 3])

    refreshed(transport)

    assert transport.paths[3:] == ["/items", "/items/14", "/items/11"]


def test_a_record_gone_with_no_count_spends_one_off_the_last(pool):
    details = [detail(WEAPONS, (200, 4, 0))]
    transport = Dtdd(by_tmdb={1078605: [WEAPONS]}, details=details, remaining=[20, 19, 18, 17, 5])
    original = transport.__call__

    def without_the_count_on_a_404(path, parameters, headers):
        try:
            return original(path, parameters, headers)
        except urllib.error.HTTPError as error:
            error.headers = None
            raise

    refreshed(without_the_count_on_a_404)

    # 5 after Weapons' lookup, then The Thing's 404 with no header makes 4, then Cube's 404 makes 3: Pulse is not asked.
    assert transport.paths[3:] == ["/items", "/items/14", "/items/11", "/items/12"]


def test_a_timeout_after_a_record_gone_still_ends_the_batch(pool):
    def timing_out_on_cube(path):
        if path == "/items/12":
            raise TimeoutError

    details = [detail(CUBE, (200, 2, 0)), detail(PULSE, (158, 1, 1)), detail(WEAPONS, (200, 4, 0))]
    before = status_of(pool["pulse"]).fetched
    transport = Dtdd(by_tmdb={1078605: [WEAPONS]}, details=details, on_call=timing_out_on_cube)

    refreshed(transport)

    assert transport.paths[3:] == ["/items", "/items/14", "/items/11", "/items/12"]
    assert status_of(pool["pulse"]).fetched == before


def test_a_failed_vocabulary_refreshes_no_film_and_keeps_the_old_vocabulary(pool):
    stored.replace_vocabulary(dtdd_client.Client("key", Dtdd()).vocabulary().value)

    def failing_on_super_categories(path):
        if path == "/topicsupercategories":
            raise TimeoutError

    transport = answering(on_call=failing_on_super_categories)

    refreshed(transport)

    assert transport.paths == VOCABULARY_PATHS
    assert Topic.objects.count() == len(VOCABULARY["/topics"])
    assert status_of(pool["weapons"]).state is State.NOT_FETCHED


def test_a_failed_lookup_never_drops_a_film_to_not_fetched(pool):
    refreshed(answering(error=TimeoutError()))

    assert [status_of(pool[film]).state for film in ["thing", "cube", "pulse"]] == [State.MATCHED] * 3


def test_a_film_withdrawn_while_dtdd_answers_stays_gone(pool):
    def withdrawing_the_thing(path):
        if path == "/items/11":
            Suggestion.objects.filter(pk=pool["thing"].pk).delete()

    refreshed(answering(on_call=withdrawing_the_thing))

    assert not Suggestion.objects.filter(pk=pool["thing"].pk).exists()
    assert not TriggerData.objects.filter(suggestion_id=pool["thing"].pk).exists()


def test_a_match_corrected_while_dtdd_answers_keeps_the_correction(pool):
    def correcting_the_thing(path):
        if path == "/items/11":
            TriggerData.objects.filter(suggestion=pool["thing"]).update(match=99, match_set_by="Iván")

    refreshed(answering(on_call=correcting_the_thing))

    status = status_of(pool["thing"])
    assert (status.match, status.set_by, status.fetched.snapshot.counts) == (99, "Iván", (TopicCount(153, 1, 0),))


def test_a_refresh_outlasting_the_move_into_run_stores_nothing(pool):
    walk_to(Phase.PICK)

    def entering_run(path):
        if path == "/items/12":
            make(Phase.PICK, Phase.RUN)

    refreshed(answering(on_call=entering_run))

    assert current() == Phase.RUN
    assert not TriggerData.objects.filter(snapshot__isnull=False).exists()
    assert not Topic.objects.exists()


def test_a_refresh_whose_vocabulary_call_outlasts_the_move_into_run_stores_no_topics(pool):
    walk_to(Phase.PICK)

    def entering_run(path):
        if path == VOCABULARY_PATHS[-1]:
            make(Phase.PICK, Phase.RUN)

    refreshed(answering(on_call=entering_run))

    assert current() == Phase.RUN
    assert not Topic.objects.exists()


# After the move commits


@pytest.fixture
def dtdd(monkeypatch):
    # The tests run with DEBUG off, so the real transport is the one the client reaches.
    def install(transport):
        monkeypatch.setattr(dtdd_client, "over_the_network", transport)
        return transport

    return install


@pytest.mark.django_db(transaction=True)
def test_the_move_commits_before_any_call_is_made(client, dtdd):
    # A transactional test, so the move's transaction is the real one and the refresh really waits for its commit.
    sign_in_as_the_admin(client)
    seen = []
    transport = dtdd(Dtdd(on_call=lambda path: seen.append((connection.in_atomic_block, list(PhaseMove.objects.values_list("phase", flat=True))))))

    response = client.post(MOVE, {"from_phase": Phase.SUGGEST, "to_phase": Phase.APPROVE})

    assert response.status_code == 302
    assert transport.paths == VOCABULARY_PATHS
    assert seen == [(False, [Phase.APPROVE])] * 3


@pytest.mark.django_db(transaction=True)
def test_a_failing_refresh_leaves_the_move_made(client, dtdd):
    sign_in_as_the_admin(client)
    transport = dtdd(Dtdd(error=TimeoutError()))

    response = client.post(MOVE, {"from_phase": Phase.SUGGEST, "to_phase": Phase.APPROVE})

    assert response.status_code == 302
    assert transport.paths == VOCABULARY_PATHS[:1]
    assert current() is Phase.APPROVE


@pytest.mark.django_db(transaction=True)
def test_a_refused_move_refreshes_nothing(client, dtdd):
    sign_in_as_the_admin(client)
    transport = dtdd(Dtdd())

    client.post(MOVE, {"from_phase": Phase.APPROVE, "to_phase": Phase.VOTE})

    assert transport.paths == []


@pytest.mark.django_db(transaction=True)
def test_a_move_refreshes_the_not_fetched_film(client, dtdd, voters):
    sign_in_as_the_admin(client)
    weapons = Suggestion.objects.suggest(voters["ada"], a_tmdb_film(1078605, "Weapons"), "Pitch.")
    dtdd(answering())

    client.post(MOVE, {"from_phase": Phase.SUGGEST, "to_phase": Phase.APPROVE})

    assert status_of(weapons).state is State.MATCHED


# The stale line


def stale_line(page):
    found = re.search(r'<p class="films-stale">(.*?)</p>', page, re.S)
    return found and found[1]


def test_the_films_tab_names_the_stale_and_unfetched_films(admin, pool):
    page = admin.get(TAB).text

    assert stale_line(page) == "Trigger data is over 25 days old for Cube and The Thing, and not yet fetched for Weapons. They refresh on the next phase move."


def test_the_films_tab_shows_no_stale_line_once_all_is_fresh(admin, pool):
    refreshed(answering())

    assert stale_line(admin.get(TAB).text) is None
