"""Entering RUN purges the trigger data, and RUN shows none; leaving RUN refreshes (#106)."""

import re

import pytest

from ribcage.phase.history import current
from ribcage.phase.models import PhaseMove
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Suggestion
from ribcage.triggers import client as dtdd_client
from ribcage.triggers import correction, stored, watched
from ribcage.triggers.models import Topic, TriggerData, WatchedTopic
from tests.http.test_match_correction import (
    ADMIN_MATCH,
    EXIT_8,
    HTMX,
    TAB,
    ask,
    films,  # noqa: F401
    dtdd,  # noqa: F401
    link,
    signed_in,
    stored_match,
    use,
)
from tests.http.test_phase import walk_to
from tests.http.test_refresh import MOVE

PICK, RUN = Phase.PICK, Phase.RUN
EXIT_8_ID = 1362774


def snapshots():
    return list(TriggerData.objects.filter(snapshot__isnull=False).values_list("suggestion_id", flat=True))


def matches():
    return {row.suggestion_id: (row.match, row.match_set_by) for row in TriggerData.objects.all()}


def into_run(admin):
    walk_to(PICK)
    admin.post(MOVE, {"from_phase": PICK, "to_phase": RUN})
    assert current() == RUN


@pytest.mark.django_db(transaction=True)
def test_entering_run_deletes_every_snapshot_and_the_vocabulary_keeps_the_matches_and_watched_lists_and_calls_nothing(admin, films, dtdd, voters):
    watched.set_ticked(voters["Hanna"], 153, True)
    watched.set_ticked(voters["Hanna"], 999999, True)
    TriggerData.objects.filter(suggestion=films["exit 8"]).update(match_set_by="Hanna")
    before = matches()
    assert snapshots() and Topic.objects.exists()
    walk_to(PICK)

    admin.post(MOVE, {"from_phase": PICK, "to_phase": RUN})

    assert current() == RUN
    assert snapshots() == [] and not Topic.objects.exists()
    assert matches() == before
    assert set(WatchedTopic.objects.filter(voter=voters["Hanna"]).values_list("topic_id", flat=True)) == {153, 999999}
    assert dtdd.paths == []


def test_a_refused_move_into_run_purges_nothing(admin, films):
    walk_to(Phase.VOTE)

    admin.post(MOVE, {"from_phase": Phase.VOTE, "to_phase": RUN})

    assert snapshots() and Topic.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_leaving_run_refreshes_the_vocabulary_and_every_film(admin, films, dtdd):
    into_run(admin)
    assert dtdd.paths == []

    admin.post(MOVE, {"from_phase": RUN, "to_phase": PICK})

    assert current() == PICK
    assert dtdd.paths
    assert Topic.objects.exists()
    assert stored.statuses_of([films["exit 8"]])[films["exit 8"].pk].fetched is not None
    assert matches()[films["exit 8"].pk] == (EXIT_8_ID, "")


def test_the_films_tab_in_run_has_no_status_line_section_or_credit(admin, films):
    before = admin.get(TAB).text
    assert "films-ledger__dtdd" in before and "Powered by DoesTheDogDie.com" in before and "dtdd__matching" in before
    into_run(admin)

    page = admin.get(TAB).text

    assert "DTDD" not in page and "films-ledger__dtdd" not in page
    assert "films-stale" not in page and "not yet fetched" not in page
    assert "film-card__dtdd" not in page and "dtdd__matching" not in page
    assert 'class="films-credit"' not in page and "dtdd__credit" not in page
    assert re.search(r'<td colspan="8">', page)


def test_the_topic_lists_answer_nothing_in_run(admin, films, voters, client):
    into_run(admin)
    pk = films["exit 8"].pk

    on_the_console = admin.get("/console/films/dtdd/", {"suggestion": pk}, headers=HTMX)
    voter = client.__class__()
    voter.force_login(voters["Hanna"])
    for_a_voter = voter.get("/dtdd/", {"suggestion": pk}, headers=HTMX)

    assert on_the_console.headers["HX-Redirect"] == TAB and not on_the_console.content
    assert for_a_voter.headers["HX-Redirect"] == "/" and not for_a_voter.content


def test_the_admins_correction_posted_in_run_saves_the_match_stores_no_snapshot_and_calls_nothing(admin, films, dtdd):
    exit_8 = films["exit 8"]
    walk_to(PICK)
    signed = signed_in(ask(admin, exit_8, link(EXIT_8), route=ADMIN_MATCH).text)
    admin.post(MOVE, {"from_phase": PICK, "to_phase": RUN})
    dtdd.paths.clear()

    response = use(admin, exit_8, signed, route=ADMIN_MATCH)

    assert response.headers["HX-Redirect"] == TAB
    assert stored_match(exit_8) == (1558416, correction.BY_THE_ADMIN)
    assert TriggerData.objects.get(suggestion=exit_8).snapshot is None
    assert dtdd.paths == []


def test_a_correction_previewed_in_run_reloads_the_tab_and_offers_no_control(admin, films, dtdd):
    into_run(admin)

    response = ask(admin, films["exit 8"], link(EXIT_8), route=ADMIN_MATCH)

    assert response.headers["HX-Redirect"] == TAB
    assert dtdd.paths == []


def phase_tab(admin, phase, to):
    return admin.get("/console/phase/", {"from": phase, "arm": to}).text


def test_the_phase_tab_prints_the_purge_and_the_refetch_on_their_moves_and_reads_the_pending_wording(admin, films):
    walk_to(PICK)
    entering = phase_tab(admin, PICK, RUN)
    assert "Every film&#x27;s trigger data is cleared, as DoesTheDogDie&#x27;s terms ask, and fetched again if the evening is unpublished." in entering
    assert 'data-pending="Moving to RUN and clearing trigger data…"' in entering
    assert "fetched again, oldest first" not in entering

    admin.post(MOVE, {"from_phase": PICK, "to_phase": RUN})
    leaving = phase_tab(admin, RUN, PICK)
    assert "Trigger data is fetched again, oldest first." in leaving
    assert 'data-pending="Moving to PICK and refreshing trigger data…"' in leaving
