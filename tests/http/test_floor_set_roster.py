"""The floor set on the Roster: its line, its column and the removal confirm's change (#28, #33, #146)."""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.ballot.models import BallotRecord
from ribcage.identity.models import Voter
from ribcage.phase.order import Phase
from ribcage.timetable.models import Timetable
from tests.http.test_ballot_page import film
from tests.http.test_phase import walk_to
from tests.http.test_removal_ballot import goes
from tests.http.test_roster_tab import TAB, text


def line(page):
    found = re.search(r'<p class="floor-line([^"]*)" data-floor-set>(.*?)</p>', page, re.S)
    return text(found[2]), "floor-line--out" in found[1]


def column(page):
    return {text(name): text(cell) for name, cell in re.findall(r'<td class="roster__name">(.*?)</td>.*?<td class="roster__floor">(.*?)</td>', page, re.S)}


@pytest.fixture
def ballot(voters):
    """VOTE open, two films: Dani scored one positively, ada only 0 and -1, Hanna nothing."""
    walk_to(Phase.VOTE)
    short, long = film(voters["Hanna"], "Short"), film(voters["Hanna"], "Long")
    Suggestion_runtime(long, 200)
    BallotRecord.objects.create(voter=voters["Dani"], suggestion=long, score=2)
    BallotRecord.objects.create(voter=voters["ada"], suggestion=short, score=0)
    BallotRecord.objects.create(voter=voters["ada"], suggestion=long, score=-1)
    return short, long


def Suggestion_runtime(suggestion, minutes):
    type(suggestion).objects.filter(pk=suggestion.pk).update(runtime=minutes)


def test_the_line_names_each_voter_out_with_the_reason_and_is_highlighted(admin, voters, ballot):
    assert line(admin.get(TAB).text) == ("Floor computed over 1 of 3 — ada: nothing representable · Hanna: no ballot", True)


def test_the_line_reads_everyone_in_and_is_not_highlighted(admin, voters, ballot):
    BallotRecord.objects.filter(voter=voters["ada"]).update(score=1)
    BallotRecord.objects.create(voter=voters["Hanna"], suggestion=ballot[0], score=3)

    assert line(admin.get(TAB).text) == ("Floor computed over 3 of 3", False)


def test_the_column_reads_in_or_the_reason_once_vote_has_opened(admin, voters, ballot):
    assert column(admin.get(TAB).text) == {"ada": "nothing representable", "Dani": "in", "Hanna": "no ballot"}


def test_the_column_reads_a_dash_before_vote_has_opened_but_the_line_is_shown(admin, voters):
    walk_to(Phase.APPROVE)

    page = admin.get(TAB).text
    assert column(page) == {"ada": "—", "Dani": "—", "Hanna": "—"}
    assert line(page) == ("Floor computed over 0 of 3 — ada: no ballot · Dani: no ballot · Hanna: no ballot", True)


def test_a_budget_below_the_only_positive_film_takes_the_voter_out(admin, voters, ballot):
    Timetable.objects.update_or_create(pk=1, defaults={"budget": 199})

    assert column(admin.get(TAB).text)["Dani"] == "nothing representable"
    assert line(admin.get(TAB).text)[0].startswith("Floor computed over 0 of 3")


def test_the_removal_confirm_shows_the_floor_sets_change(admin, voters, ballot):
    assert goes(admin.get(TAB, {"remove": voters["Hanna"].pk}).text)[-1] == "The floor set goes from 1 of 3 to 1 of 2."
    assert goes(admin.get(TAB, {"remove": voters["Dani"].pk}).text)[-1] == "The floor set goes from 1 of 3 to 0 of 2."


def test_the_tab_makes_no_more_queries_for_more_voters(admin, voters, ballot):
    def queries():
        with CaptureQueriesContext(connection) as captured:
            assert admin.get(TAB).status_code == 200
        return len(captured)

    small = queries()
    for name in ["Eve", "Fay", "Gus"]:
        voter = Voter.objects.create_voter(name, "a-password-123")
        BallotRecord.objects.create(voter=voter, suggestion=ballot[0], score=2)

    assert queries() == small
