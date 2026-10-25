"""The ballot page and its place route: Unsorted, the five bands and the one write that places a film (#9, #119)."""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.ballot.models import BallotRecord
from ribcage.phase.history import move
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.triggers import watched
from tests.http.test_matched_topics import DOG, add, dtdd, signed_in, vocabulary  # noqa: F401
from tests.http.test_phase import walk_to

PLACE = "/ballot/place/"
HTMX = {"HX-Request": "true"}


def film(voter, title, approval=Approval.APPROVED):
    return Suggestion.objects.create(title=title, suggester=voter, suggester_name=voter.display_name, approval=approval, runtime=100)


def approved(suggestion):
    Suggestion.objects.filter(pk=suggestion.pk).update(approval=Approval.APPROVED)
    return suggestion


def place(client, suggestion, to, **extra):
    return client.post(PLACE, {"suggestion": str(suggestion.pk), "to": str(to)}, **extra)


def region(page, name):
    """The tile ids inside the list a placement names: the tray, or a band by its score."""
    block = re.search(rf'<ul class="tiles [a-z_-]+" data-place="{name}".*?</ul>', page, re.S)[0]
    return [int(pk) for pk in re.findall(r'data-suggestion="(\d+)"', block)]


def tiles_on(page):
    return [int(pk) for pk in re.findall(r'<li class="tile[^"]*" data-suggestion="(\d+)"', page)]


@pytest.fixture
def ballot(voters):
    walk_to(Phase.VOTE)
    ada, hanna = voters["ada"], voters["Hanna"]
    return {
        "ada": ada,
        "client": signed_in(ada),
        "one": film(hanna, "One"),
        "two": film(hanna, "Two"),
        "three": film(hanna, "Three"),
        "dropped": film(hanna, "Dropped", Approval.DROPPED),
        "undecided": film(hanna, "Undecided", Approval.UNDECIDED),
    }


def score_of(voter, suggestion):
    return BallotRecord.objects.filter(voter=voter, suggestion=suggestion).values_list("score", flat=True).first()


def test_the_ballot_is_the_approved_films_and_every_one_starts_in_the_tray(ballot):
    page = ballot["client"].get("/").text

    assert sorted(region(page, "unsorted")) == sorted([ballot["one"].pk, ballot["two"].pk, ballot["three"].pk])
    assert sorted(tiles_on(page)) == sorted(region(page, "unsorted"))
    assert "0 of 3 scored" in page and "3 left" in page
    assert re.search(r"<h1>Vote</h1>", page)


def test_the_header_says_the_standing_line_and_the_bands_run_from_top_pick_to_rather_not(ballot):
    page = ballot["client"].get("/").text

    assert "Your scores aren't shown to the group while VOTE is open. Everyone's scores are shown, by name, once it closes." in page
    assert re.findall(r'data-place="(-?\w+)"', page) == ["unsorted", "3", "2", "1", "0", "-1", "veto"]


@pytest.mark.parametrize("score", [3, 2, 1, 0, -1])
def test_a_placement_sets_a_score_and_the_page_shows_the_tile_in_its_band(ballot, score):
    place(ballot["client"], ballot["one"], score)

    page = ballot["client"].get("/").text
    assert score_of(ballot["ada"], ballot["one"]) == score
    assert region(page, str(score)) == [ballot["one"].pk]
    assert ballot["one"].pk not in region(page, "unsorted")
    assert "1 of 3 scored" in page and "2 left" in page


def test_a_placement_replaces_a_score_and_a_placement_to_unsorted_clears_it(ballot):
    place(ballot["client"], ballot["one"], 3)
    place(ballot["client"], ballot["one"], -1)
    assert score_of(ballot["ada"], ballot["one"]) == -1

    place(ballot["client"], ballot["one"], "unsorted")

    assert not BallotRecord.objects.exists()
    assert ballot["one"].pk in region(ballot["client"].get("/").text, "unsorted")


def test_a_repeated_placement_changes_nothing(ballot):
    for _ in range(3):
        place(ballot["client"], ballot["one"], 2)
    for _ in range(2):
        place(ballot["client"], ballot["two"], "unsorted")

    assert list(BallotRecord.objects.values_list("suggestion_id", "score")) == [(ballot["one"].pk, 2)]


def test_a_placement_to_unsorted_keeps_a_record_that_holds_seen_it_and_deletes_the_rest(ballot):
    BallotRecord.objects.create(voter=ballot["ada"], suggestion=ballot["one"], score=2, seen_it=True)
    BallotRecord.objects.create(voter=ballot["ada"], suggestion=ballot["two"], score=2)

    place(ballot["client"], ballot["one"], "unsorted")
    place(ballot["client"], ballot["two"], "unsorted")

    record = BallotRecord.objects.get()
    assert (record.suggestion_id, record.score, record.seen_it) == (ballot["one"].pk, None, True)


def test_a_placement_onto_a_score_replaces_a_veto_and_its_reason(ballot):
    BallotRecord.objects.create(voter=ballot["ada"], suggestion=ballot["one"], vetoed=True, veto_reason="No.")

    place(ballot["client"], ballot["one"], 1)

    record = BallotRecord.objects.get()
    assert (record.score, record.vetoed, record.veto_reason) == (1, False, None)


def test_a_vetoed_record_counts_as_placed_and_is_not_in_the_tray(ballot):
    BallotRecord.objects.create(voter=ballot["ada"], suggestion=ballot["one"], vetoed=True)
    place(ballot["client"], ballot["two"], 3)

    page = ballot["client"].get("/").text

    assert "2 of 3 scored" in page and "1 left" in page
    assert region(page, "unsorted") == [ballot["three"].pk]


def test_an_answer_to_htmx_carries_the_two_counts_out_of_band(ballot):
    answer = place(ballot["client"], ballot["one"], 3, headers=HTMX)

    assert answer.status_code == 200
    assert '<p class="ballot-head__scored" id="ballot-scored" hx-swap-oob="true">1 of 3 scored</p>' in answer.text
    assert 'id="tray-left" hx-swap-oob="true"><b>2 left</b>' in answer.text


def test_an_answer_counts_a_vetoed_record_as_the_page_does(ballot):
    BallotRecord.objects.create(voter=ballot["ada"], suggestion=ballot["one"], vetoed=True)

    answer = place(ballot["client"], ballot["two"], 3, headers=HTMX)
    page = ballot["client"].get("/").text

    assert ">2 of 3 scored<" in answer.text and "<b>1 left</b>" in answer.text
    assert "2 of 3 scored" in page and "1 left" in page


def test_a_plain_post_is_answered_with_the_ballot(ballot):
    assert place(ballot["client"], ballot["one"], 3)["Location"] == "/"


def walk_on_to(phase):
    steps = {Phase.APPROVE: [(Phase.VOTE, Phase.APPROVE)], Phase.SUGGEST: [(Phase.VOTE, Phase.APPROVE), (Phase.APPROVE, Phase.SUGGEST)], Phase.PICK: [(Phase.VOTE, Phase.PICK)], Phase.RUN: [(Phase.VOTE, Phase.PICK), (Phase.PICK, Phase.RUN)]}
    for before, after in steps[phase]:
        move(before, after)


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE, Phase.PICK, Phase.RUN])
def test_a_placement_outside_vote_writes_nothing_and_reloads_the_tab(ballot, phase):
    walk_on_to(phase)

    answer = place(ballot["client"], ballot["one"], 3, headers=HTMX)

    assert answer["HX-Redirect"] == "/"
    assert not BallotRecord.objects.exists()


def test_a_placement_on_a_film_dropped_since_the_page_loaded_changes_nothing_and_reloads_onto_the_ballot(ballot):
    answer = place(ballot["client"], ballot["dropped"], 3, headers=HTMX)

    assert answer["HX-Redirect"] == "/"
    assert not BallotRecord.objects.exists()
    assert place(ballot["client"], ballot["dropped"], 3)["Location"] == "/"


@pytest.mark.parametrize(
    "posted",
    [
        {"suggestion": "x", "to": "3"},
        {"suggestion": "999999", "to": "3"},
        {"to": "3"},
        {"suggestion": "{one}", "to": "4"},
        {"suggestion": "{one}", "to": "Veto"},
        {"suggestion": "{one}", "to": "2.5"},
        {"suggestion": "{one}"},
    ],
)
def test_a_post_naming_no_candidate_or_no_target_changes_nothing_and_reloads(ballot, posted):
    posted = {name: value.replace("{one}", str(ballot["one"].pk)) for name, value in posted.items()}

    answer = ballot["client"].post(PLACE, posted, headers=HTMX)

    assert answer["HX-Redirect"] == "/"
    assert not BallotRecord.objects.exists()


def test_the_place_route_answers_post_alone(ballot):
    assert ballot["client"].get(PLACE).status_code == 405


def test_a_dropped_films_record_is_kept_and_returns_when_it_is_approved_again(ballot):
    place(ballot["client"], ballot["one"], 3)
    Suggestion.objects.filter(pk=ballot["one"].pk).update(approval=Approval.DROPPED)
    page = ballot["client"].get("/").text
    assert ballot["one"].pk not in tiles_on(page) and "0 of 2 scored" in page

    approved(ballot["one"])

    assert region(ballot["client"].get("/").text, "3") == [ballot["one"].pk]


def test_a_voter_sees_only_their_own_placements(ballot, voters):
    place(ballot["client"], ballot["one"], 3)

    page = signed_in(voters["Dani"]).get("/").text

    assert region(page, "3") == [] and "0 of 3 scored" in page


def test_an_empty_ballot_says_so_in_one_line_and_the_bands_still_show(voters):
    walk_to(Phase.VOTE)
    film(voters["Hanna"], "Undecided", Approval.UNDECIDED)

    page = signed_in(voters["ada"]).get("/").text

    assert "Nothing is on the ballot yet." in page and "0 of 0 scored" in page
    assert page.count('class="band band--') == 6


def test_the_tray_lists_matched_films_first_and_each_group_in_the_voters_fixed_order(voters, vocabulary):  # noqa: F811
    walk_to(Phase.VOTE)
    ada = voters["ada"]
    watched.set_ticked(ada, DOG, True)
    plain = [film(voters["Hanna"], f"Plain {number}") for number in range(6)]
    weak = approved(add(voters["Hanna"], "Weak", dog=(1, 0)))
    ringed = approved(add(voters["Hanna"], "Ringed", dog=(12, 1)))

    first = region(signed_in(ada).get("/").text, "unsorted")

    assert set(first[:2]) == {weak.pk, ringed.pk}
    assert set(first[2:]) == {each.pk for each in plain}
    assert region(signed_in(ada).get("/").text, "unsorted") == first
    assert region(signed_in(voters["Dani"]).get("/").text, "unsorted")[2:] != first[2:]


def test_a_tick_made_meanwhile_moves_nothing_until_the_page_loads_again(voters, vocabulary):  # noqa: F811
    walk_to(Phase.VOTE)
    ada = voters["ada"]
    film(voters["Hanna"], "Plain")
    ringed = approved(add(voters["Hanna"], "Ringed", dog=(12, 1)))

    before = region(signed_in(ada).get("/").text, "unsorted")
    watched.set_ticked(ada, DOG, True)
    after = region(signed_in(ada).get("/").text, "unsorted")

    assert after[0] == ringed.pk and sorted(before) == sorted(after)


def test_a_ringed_tile_carries_the_ring_and_the_count_and_only_for_a_voter_who_watches(voters, vocabulary):  # noqa: F811
    walk_to(Phase.VOTE)
    approved(add(voters["Hanna"], "Ringed", dog=(12, 1)))
    watched.set_ticked(voters["ada"], DOG, True)

    def tile(voter):
        return re.search(r'<li class="tile[^"]*"[^>]*>.*?</li>', signed_in(voter).get("/").text, re.S)[0]

    assert "has-trigger-icon" in tile(voters["ada"]) and 'aria-label="1 of your warnings"' in tile(voters["ada"])
    assert "has-trigger-icon" not in tile(voters["Dani"]) and "trigger-count" not in tile(voters["Dani"])
    watched.stop_caring(voters["ada"])
    assert "has-trigger-icon" not in tile(voters["ada"])


def test_a_tile_holds_the_poster_the_title_and_the_year_and_nothing_else(ballot):
    tile = re.search(r'<li class="tile[^"]*" data-suggestion="\d+">(.*?)</li>', ballot["client"].get("/").text, re.S)[1]

    assert re.findall(r'class="(tile__[a-z]+|poster[^"]*)"', tile)[-1] == "tile__title"
    # The seen-it toggle is the tile's one control (#121).
    assert re.findall(r"<button[^>]*>", tile) == [re.search(r'<button type="button" class="seen-toggle[^>]*>', tile)[0]] and "<a " not in tile and "<form" not in tile


def test_the_pages_query_count_does_not_grow_with_the_ballot(voters, vocabulary):  # noqa: F811
    walk_to(Phase.VOTE)
    ada = voters["ada"]
    watched.set_ticked(ada, DOG, True)

    def queries():
        client = signed_in(ada)
        with CaptureQueriesContext(connection) as captured:
            client.get("/")
        return len(captured)

    for number in range(2):
        suggestion = approved(add(voters["Hanna"], f"Early {number}", dog=(12, 1)))
    BallotRecord.objects.create(voter=ada, suggestion=suggestion, score=1)
    small = queries()
    for number in range(12):
        suggestion = approved(add(voters["Hanna"], f"Late {number}", dog=(12, 1)))
        if number % 2:
            BallotRecord.objects.create(voter=ada, suggestion=suggestion, score=number % 4)

    assert queries() == small


def test_the_ballot_is_no_page_outside_vote(voters):
    walk_to(Phase.PICK)

    assert "data-board" not in signed_in(voters["ada"]).get("/").text
