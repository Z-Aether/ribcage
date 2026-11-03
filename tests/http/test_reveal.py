"""The reveal in PICK: everyone's scores by name, for each film on the ballot (#29, #154)."""

import re

from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.ballot.models import BallotRecord
from ribcage.identity.models import Voter
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Note
from tests.http.test_ballot_page import film
from tests.http.test_matched_topics import signed_in
from tests.http.test_phase import walk_to


def mark(voter, suggestion, **fields):
    BallotRecord.objects.create(voter=voter, suggestion=suggestion, **fields)


def titles_down(page):
    return re.findall(r'<span class="reveal__title-line">([^<]*?)(?: <span|</span>)', page)


def header_names(page):
    return re.findall(r'<span class="reveal__name">([^<]*)</span>', page)


def row_of(page, suggestion):
    return re.search(rf'<tr class="reveal__row" data-suggestion="{suggestion.pk}">.*?</tr>', page, re.S)[0]


def cells_of(row):
    return re.findall(r'<td class="reveal__cell[^"]*">(.*?)</td>', row, re.S)


def revealed(voters):
    walk_to(Phase.PICK)
    hanna = voters["Hanna"]
    return {"hanna": hanna, "ada": voters["ada"], "dani": voters["Dani"], "one": film(hanna, "One"), "two": film(hanna, "Two"), "dropped": film(hanna, "Dropped", Approval.DROPPED)}


def test_a_row_for_each_approved_film_and_none_for_a_dropped_film_that_keeps_its_scores(voters):
    data = revealed(voters)
    mark(data["ada"], data["dropped"], score=3)
    mark(data["ada"], data["one"], score=1)

    page = signed_in(data["ada"]).get("/").text

    assert 'class="reveal__row"' in page
    assert f'data-suggestion="{data["dropped"].pk}"' not in page
    assert titles_down(page) == ["One", "Two"]


def test_the_page_keeps_the_heading_the_phase_pins(voters):
    data = revealed(voters)

    page = signed_in(data["ada"]).get("/").text

    assert re.search(r"<h1>(.*?)</h1>", page)[1] == "Voting is closed"
    assert "everyone's scores are open, by name" in page


def test_every_voter_has_a_column_in_the_rosters_case_blind_order(voters):
    data = revealed(voters)

    page = signed_in(data["dani"]).get("/").text

    assert header_names(page) == ["ada", "Dani", "Hanna"]


def test_the_viewers_own_column_is_tinted_and_no_one_elses(voters):
    data = revealed(voters)

    page = signed_in(data["dani"]).get("/").text

    assert len(re.findall(r'class="reveal__voter is-mine', page)) == 1
    assert re.search(rf'class="reveal__voter is-mine[^"]*" data-voter="{data["dani"].pk}"', page)
    assert [cell.count("is-mine") for cell in re.findall(r'<td class="reveal__cell[^"]*"', page)[:3]] == [0, 1, 0]


def test_a_score_a_veto_a_blank_and_seen_it_each_have_their_cell(voters):
    data = revealed(voters)
    mark(data["ada"], data["one"], score=3, seen_it=True)
    mark(data["dani"], data["one"], vetoed=True)
    Note.objects.create(suggestion=data["one"], author=data["dani"], text="Not for me.")

    row = row_of(signed_in(data["ada"]).get("/").text, data["one"])
    ada, dani, hanna = cells_of(row)

    assert "reveal-pill--top-pick" in ada and "+3" in ada and "reveal-pill__seen" in ada
    assert "reveal-pill--veto" in dani and "☒" in dani and "Not for me." in dani and "reveal-pill__seen" not in dani
    assert "reveal-pill--blank" in hanna and "reveal-pill__seen" not in hanna
    visible = re.sub(r"<[^>]*>", "", re.sub(r'<span class="visually-hidden">.*?</span>', "", hanna)).strip()
    assert visible == ""
    assert "☒ Dani" in row


def test_a_voter_with_nothing_placed_is_headed_didnt_vote_and_a_partial_one_reads_n_of_m(voters):
    data = revealed(voters)
    mark(data["ada"], data["one"], score=2)
    mark(data["dani"], data["one"], vetoed=True)
    mark(data["dani"], data["two"], score=1)
    mark(data["hanna"], data["two"], seen_it=True)

    page = signed_in(data["ada"]).get("/").text
    heads = dict(zip(header_names(page), re.findall(r'<th scope="col" class="reveal__voter[^>]*>(.*?)</th>', page, re.S), strict=True))

    assert "1 of 2" in heads["ada"]
    assert "didn't vote" in heads["Hanna"]
    assert "didn't vote" not in heads["Dani"] and "of 2" not in heads["Dani"]


def test_the_rows_run_by_points_and_the_points_count_a_veto_at_minus_two(voters):
    data = revealed(voters)
    mark(data["ada"], data["two"], score=1)
    mark(data["dani"], data["one"], vetoed=True)

    page = signed_in(data["ada"]).get("/").text

    assert titles_down(page) == ["Two", "One"]
    assert re.findall(r"<b>(-?\d+)</b>", page) == ["1", "-2"]


def test_the_floor_set_is_not_mentioned(voters):
    data = revealed(voters)

    assert "floor" not in signed_in(data["ada"]).get("/").text.lower()


def test_the_query_count_stays_flat_as_voters_and_films_grow(voters):
    data = revealed(voters)

    def queries():
        with CaptureQueriesContext(connection) as captured:
            signed_in(data["ada"]).get("/")
        return len(captured)

    small = queries()
    for number in range(4):
        voter = Voter.objects.create_voter(f"Extra {number}", "x")
        new = film(data["hanna"], f"Extra film {number}")
        mark(voter, new, score=2)
        mark(voter, data["one"], vetoed=True)
        Note.objects.create(suggestion=new, author=voter, text="Hello.")

    assert queries() == small


def test_a_voter_header_carries_the_full_name_as_its_title(voters):
    data = revealed(voters)

    page = signed_in(data["ada"]).get("/").text

    assert 'title="ada"' in page
