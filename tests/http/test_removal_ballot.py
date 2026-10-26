"""Removal deletes a voter's ballot records and done marker, and the confirm lists them only when present (#28, #98, #118)."""

import re

import pytest

from ribcage.ballot.models import BallotRecord, DoneMarker
from ribcage.suggestions.models import Note, Suggestion
from tests.films import a_tmdb_film
from tests.http.test_roster_tab import TAB, text

REMOVE = "/console/roster/remove/"


def goes(page):
    return [text(item) for item in re.findall(r'<li class="roster-confirm__goes">(.*?)</li>', page, re.S)]


def has_ballot(voter):
    return BallotRecord.objects.filter(voter_id=voter.pk).exists() or DoneMarker.objects.filter(voter_id=voter.pk).exists()


@pytest.fixture
def films(voters):
    thing = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing"), "Lights off.")
    cube = Suggestion.objects.suggest(voters["ada"], a_tmdb_film(431, "Cube"), "Six strangers.")
    rope = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1092, "Rope"), "One take.")
    return thing, cube, rope


@pytest.fixture
def voted(voters, films):
    # Ada: two scores, a veto, two seen-it flags and done. Dani: one score on Ada's film.
    thing, cube, rope = films
    ada, dani = voters["ada"], voters["Dani"]
    BallotRecord.objects.create(voter=ada, suggestion=thing, score=3, seen_it=True)
    BallotRecord.objects.create(voter=ada, suggestion=cube, score=-1)
    BallotRecord.objects.create(voter=ada, suggestion=rope, vetoed=True, seen_it=True)
    Note.objects.create(suggestion=rope, author=ada, text="No.")
    BallotRecord.objects.create(voter=dani, suggestion=cube, score=2)
    DoneMarker.objects.create(voter=ada)
    DoneMarker.objects.create(voter=dani)


def test_removing_a_voter_deletes_their_records_and_done_marker_and_keeps_the_others(admin, voters, films, voted):
    admin.post(REMOVE, {"voter": voters["ada"].pk})

    assert not has_ballot(voters["ada"])
    assert list(BallotRecord.objects.values_list("voter__display_name", "suggestion__title", "score")) == [("Dani", "Cube", 2)]
    assert list(DoneMarker.objects.values_list("voter__display_name", flat=True)) == ["Dani"]
    assert Suggestion.objects.count() == 3


def test_the_confirm_lists_scores_vetoes_seen_it_flags_and_the_done_marker(admin, voters, voted):
    page = admin.get(TAB, {"remove": voters["ada"].pk}).text

    assert goes(page)[2] == "their 2 scores, 1 veto and 2 seen-it flags"
    assert goes(page)[3] == "their done marker"


def test_the_confirm_lists_only_what_the_voter_has(admin, voters, voted):
    dani = goes(admin.get(TAB, {"remove": voters["Dani"].pk}).text)
    assert dani[2:4] == ["their 1 score", "their done marker"]

    DoneMarker.objects.filter(voter=voters["Dani"]).delete()
    assert goes(admin.get(TAB, {"remove": voters["Dani"].pk}).text)[2:] == ["their 1 score"]


def test_the_confirm_says_nothing_of_a_ballot_the_voter_never_touched(admin, voters, voted):
    hanna = goes(admin.get(TAB, {"remove": voters["Hanna"].pk}).text)

    assert not any("score" in each or "veto" in each or "seen" in each or "done" in each for each in hanna)
