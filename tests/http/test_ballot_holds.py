"""A ballot record holds its film: no withdraw, no pencil, no cleared runtime (#34, #89, #90, #97, #118)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.ballot.models import BallotRecord
from ribcage.phase.history import move
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Suggestion
from tests.films import a_tmdb_film
from tests.http.test_films_tab import suggested
from tests.http.test_phase import walk_to
from tests.http.test_runtime_box import EDIT, HELD, box, stored
from tests.http.test_runtime_pencil import pencils_on
from tests.http.test_withdraw import arms_on

HTMX = {"HX-Request": "true"}
RECORDS = {
    "a score": {"score": 2},
    "only a veto": {"vetoed": True},
    "only seen it": {"seen_it": True},
}


def back_in_suggest():
    # #34's backwards seam: a film that gathered records in VOTE is in the pool again.
    walk_to(Phase.VOTE)
    move(Phase.VOTE, Phase.APPROVE)
    move(Phase.APPROVE, Phase.SUGGEST)


@pytest.fixture
def pair(voters):
    held = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing", runtime=109), "Lights off.")
    free = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(431, "Cube", runtime=90), "Six strangers.")
    return held, free


@pytest.mark.parametrize("fields", RECORDS.values(), ids=RECORDS.keys())
def test_a_film_with_a_record_offers_neither_withdraw_nor_the_pencil(client, voters, pair, fields):
    held, free = pair
    BallotRecord.objects.create(voter=voters["ada"], suggestion=held, **fields)
    back_in_suggest()
    client.force_login(voters["Hanna"])

    page = client.get("/").text

    assert arms_on(page) == [free.pk]
    assert pencils_on(page) == [free.pk]


@pytest.mark.parametrize("fields", RECORDS.values(), ids=RECORDS.keys())
def test_a_stale_withdraw_or_pencil_on_it_is_refused_and_changes_nothing(client, voters, pair, fields):
    held, _ = pair
    BallotRecord.objects.create(voter=voters["ada"], suggestion=held, **fields)
    back_in_suggest()
    client.force_login(voters["Hanna"])

    client.post("/withdraw/", {"suggestion": held.pk}, headers=HTMX)
    client.post("/runtime/", {"suggestion": held.pk, "runtime": "127"}, headers=HTMX)

    assert Suggestion.objects.filter(pk=held.pk, runtime=109, tmdb_runtime=109).exists()


def test_the_films_tab_refuses_to_clear_a_dropped_film_with_a_record_and_clears_one_without(admin, voters):
    walk_to(Phase.APPROVE)
    held = suggested(voters["Hanna"], "Cube", Approval.DROPPED, runtime=90)
    free = suggested(voters["Hanna"], "Rope", Approval.DROPPED, runtime=80)
    BallotRecord.objects.create(voter=voters["ada"], suggestion=held, seen_it=True)

    refused = admin.post(EDIT, {"suggestion": held.pk, "runtime": ""})
    cleared = admin.post(EDIT, {"suggestion": free.pk, "runtime": ""})

    assert refused.status_code == 200
    assert HELD in box(refused.text, held)[4]
    assert stored(held) == (90, 90)
    assert cleared.status_code == 302
    assert stored(free) == (None, 80)


def test_the_pool_makes_no_more_queries_for_more_records(client, voters, pair):
    client.force_login(voters["Dani"])

    def queries():
        with CaptureQueriesContext(connection) as captured:
            assert client.get("/").status_code == 200
        return len(captured)

    small = queries()
    for title, tmdb in [("Two", 2), ("Three", 3), ("Four", 4)]:
        film = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(tmdb, title), "A pitch.")
        BallotRecord.objects.create(voter=voters["ada"], suggestion=film, score=1)

    assert queries() == small
