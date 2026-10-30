"""Only a score holds its film from the ballot: no withdraw, no pencil, no cleared runtime; a veto or seen it alone holds nothing (#34, #89, #90, #97, #118, #151)."""

import pytest
from django.db import connection
from django.db.models import ProtectedError
from django.test.utils import CaptureQueriesContext

from ribcage.ballot.models import BallotRecord
from ribcage.phase.history import move
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.suggestions.withdrawal import withdraw
from tests.films import a_tmdb_film
from tests.http.test_films_tab import suggested
from tests.http.test_phase import walk_to
from tests.http.test_runtime_box import EDIT, HELD, box, stored
from tests.http.test_runtime_pencil import pencils_on
from tests.http.test_withdraw import arms_on

HTMX = {"HX-Request": "true"}
RECORDS = {
    "a score": {"score": 2},
    "a score and seen it": {"score": 2, "seen_it": True},
}
MARKS = {
    "only a veto": {"vetoed": True},
    "only seen it": {"seen_it": True},
    "a veto and seen it": {"vetoed": True, "seen_it": True},
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


def test_the_films_tab_refuses_to_clear_a_dropped_film_with_a_score_and_clears_one_without(admin, voters):
    walk_to(Phase.APPROVE)
    held = suggested(voters["Hanna"], "Cube", Approval.DROPPED, runtime=90)
    free = suggested(voters["Hanna"], "Rope", Approval.DROPPED, runtime=80)
    BallotRecord.objects.create(voter=voters["ada"], suggestion=held, score=1, seen_it=True)

    refused = admin.post(EDIT, {"suggestion": held.pk, "runtime": ""})
    cleared = admin.post(EDIT, {"suggestion": free.pk, "runtime": ""})

    assert refused.status_code == 200
    assert HELD in box(refused.text, held)[4]
    assert stored(held) == (90, 90)
    assert cleared.status_code == 302
    assert stored(free) == (None, 80)


def test_the_films_tab_clears_the_runtime_of_an_unscored_vetoed_film(admin, voters):
    walk_to(Phase.APPROVE)
    film = suggested(voters["Hanna"], "Cube", Approval.DROPPED, runtime=90)
    BallotRecord.objects.create(voter=voters["ada"], suggestion=film, vetoed=True)
    BallotRecord.objects.create(voter=voters["Dani"], suggestion=film, seen_it=True)

    cleared = admin.post(EDIT, {"suggestion": film.pk, "runtime": ""})

    assert cleared.status_code == 302
    assert stored(film) == (None, 90)


@pytest.mark.parametrize("fields", MARKS.values(), ids=MARKS.keys())
def test_a_film_with_only_vetoes_and_seen_its_offers_withdraw_and_the_pencil(client, voters, pair, fields):
    held, free = pair
    BallotRecord.objects.create(voter=voters["ada"], suggestion=held, **fields)
    back_in_suggest()
    client.force_login(voters["Hanna"])

    page = client.get("/").text

    assert set(arms_on(page)) == {held.pk, free.pk}
    assert set(pencils_on(page)) == {held.pk, free.pk}


def test_withdrawing_it_deletes_those_records_with_the_film_and_leaves_other_films(client, voters, pair):
    held, free = pair
    BallotRecord.objects.create(voter=voters["ada"], suggestion=held, vetoed=True, seen_it=True)
    BallotRecord.objects.create(voter=voters["Hanna"], suggestion=held, seen_it=True)
    BallotRecord.objects.create(voter=voters["ada"], suggestion=free, vetoed=True)
    back_in_suggest()
    client.force_login(voters["Hanna"])

    client.post("/withdraw/", {"suggestion": held.pk}, headers=HTMX)

    assert not Suggestion.objects.filter(pk=held.pk).exists()
    assert not BallotRecord.objects.filter(suggestion_id=held.pk).exists()
    assert BallotRecord.objects.filter(suggestion=free).count() == 1


def test_the_confirm_counts_the_groups_marks_and_leaves_the_suggesters_own_out(client, voters, pair):
    held, _ = pair
    BallotRecord.objects.create(voter=voters["ada"], suggestion=held, vetoed=True, seen_it=True)
    BallotRecord.objects.create(voter=voters["Dani"], suggestion=held, vetoed=True)
    BallotRecord.objects.create(voter=voters["Hanna"], suggestion=held, vetoed=True, seen_it=True)
    back_in_suggest()
    client.force_login(voters["Hanna"])

    armed = client.get("/withdraw/", {"suggestion": held.pk}, headers=HTMX).text

    assert "your pitch, 2 vetoes and a seen-it flag from the group" in armed


def test_a_scored_record_a_hold_missed_still_fails_the_delete_loudly(voters, pair):
    held, _ = pair
    BallotRecord.objects.create(voter=voters["ada"], suggestion=held, score=2)

    with pytest.raises(ProtectedError):
        held.delete()


def test_withdraw_spares_a_scored_record_a_hold_missed_and_rolls_back_the_unscored_delete(voters, pair):
    held, _ = pair
    scored = BallotRecord.objects.create(voter=voters["ada"], suggestion=held, score=2)
    unscored = BallotRecord.objects.create(voter=voters["Dani"], suggestion=held, vetoed=True)

    with pytest.raises(ProtectedError):
        withdraw(held)

    assert Suggestion.objects.filter(pk=held.pk).exists()
    assert BallotRecord.objects.filter(pk__in=[scored.pk, unscored.pk]).count() == 2


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
