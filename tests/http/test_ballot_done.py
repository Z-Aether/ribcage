"""I'm done and the done roster: a voter's own signal, shown to the whole group by name and nothing finer (#15, #35, #123)."""

import re

import pytest

from ribcage.ballot.models import BallotRecord, DoneMarker
from ribcage.phase.history import move
from ribcage.phase.order import Phase
from tests.http.test_ballot_page import HTMX, film, place, signed_in, walk_on_to
from tests.http.test_phase import walk_to

DONE = "/ballot/done/"


def post(client, state, **extra):
    return client.post(DONE, {"done": state}, **extra)


def roster_of(page):
    """The roster as (name, ticked) in page order, and its count line."""
    block = re.search(r'<ul class="ballot-done__roster">(.*?)</ul>', page, re.S)[0]
    names = [(re.sub(r"<.*?>|[✓]", "", item).strip(), "ballot-done__tick" in item and "aria-hidden" not in item) for item in re.findall(r"<li.*?</li>", block, re.S)]
    return names, re.search(r'ballot-done__count">(.*?)</p>', page)[1]


@pytest.fixture
def ballot(voters):
    walk_to(Phase.VOTE)
    film(voters["Hanna"], "One")
    return voters


def marked(voter):
    return DoneMarker.objects.filter(voter=voter).exists()


def test_im_done_sets_and_unsets_the_marker_and_a_repeat_changes_nothing(ballot):
    client = signed_in(ballot["ada"])

    post(client, "1")
    post(client, "1")
    assert DoneMarker.objects.filter(voter=ballot["ada"]).count() == 1
    post(client, "0")
    post(client, "0")

    assert not marked(ballot["ada"])


def test_the_answer_draws_the_header_block_with_the_state_it_set(ballot):
    client = signed_in(ballot["ada"])

    on = post(client, "1", headers=HTMX).text
    off = post(client, "0", headers=HTMX).text

    assert 'aria-pressed="true"' in on and "1 of" in on and 'name="done" value="0"' in on
    assert 'aria-pressed="false"' in off and "0 of" in off and 'name="done" value="1"' in off


def test_a_plain_post_redirects_to_the_page(ballot):
    answer = post(signed_in(ballot["ada"]), "1")

    assert answer.status_code == 302 and marked(ballot["ada"])


def test_being_done_leaves_the_ballot_editable_and_unsorted_films_stay_unsorted(ballot):
    client = signed_in(ballot["ada"])
    one = film(ballot["Hanna"], "Two")

    post(client, "1")
    place(client, one, 2)

    assert marked(ballot["ada"]) and BallotRecord.objects.get(voter=ballot["ada"], suggestion=one).score == 2


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE, Phase.PICK, Phase.RUN])
def test_a_post_outside_vote_reloads_the_tab_and_writes_nothing(ballot, phase):
    walk_on_to(phase)

    answer = post(signed_in(ballot["ada"]), "1", headers=HTMX)

    assert answer.headers["HX-Redirect"] and not DoneMarker.objects.exists()


def test_an_unnamed_state_reloads_and_writes_nothing(ballot):
    for state in ("", "maybe"):
        assert "HX-Redirect" in post(signed_in(ballot["ada"]), state, headers=HTMX).headers
    assert not DoneMarker.objects.exists()


def test_every_voters_ballot_lists_the_same_roster_by_name_with_the_done_ticked(ballot):
    DoneMarker.objects.create(voter=ballot["Dani"])
    DoneMarker.objects.create(voter=ballot["Hanna"])

    seen = {name: roster_of(signed_in(voter).get("/").text) for name, voter in ballot.items()}

    assert len({repr(each) for each in seen.values()}) == 1
    names, count = seen["ada"]
    assert [name for name, _ in names] == sorted((voter.display_name for voter in ballot.values()), key=str.casefold)
    assert {name for name, ticked in names if ticked} == {ballot["Dani"].display_name, ballot["Hanna"].display_name}
    assert count == f"2 of {len(ballot)} done"


def test_the_roster_shows_done_and_nothing_finer(ballot):
    one = film(ballot["Hanna"], "Two")
    place(signed_in(ballot["Dani"]), one, 3)

    page = signed_in(ballot["ada"]).get("/").text
    names, _ = roster_of(page)

    assert (ballot["Dani"].display_name, False) in names


def test_a_removed_voter_leaves_the_roster_and_the_count(ballot):
    DoneMarker.objects.create(voter=ballot["Dani"])
    before = roster_of(signed_in(ballot["ada"]).get("/").text)

    ballot["Dani"].delete()
    names, count = roster_of(signed_in(ballot["ada"]).get("/").text)

    assert len(names) == len(before[0]) - 1 and count == f"0 of {len(names)} done"


def test_a_phase_move_away_from_vote_and_back_keeps_every_marker(ballot):
    DoneMarker.objects.create(voter=ballot["ada"])
    DoneMarker.objects.create(voter=ballot["Dani"])

    move(Phase.VOTE, Phase.PICK)
    move(Phase.PICK, Phase.VOTE)
    move(Phase.VOTE, Phase.APPROVE)
    move(Phase.APPROVE, Phase.VOTE)

    assert set(DoneMarker.objects.values_list("voter__display_name", flat=True)) == {ballot["ada"].display_name, ballot["Dani"].display_name}


def test_the_toggle_morphs_its_block_so_the_focused_button_survives(ballot):
    form = re.search(r'<form class="ballot-done__toggle".*?>', signed_in(ballot["ada"]).get("/").text)[0]

    assert 'hx-swap="morph:outerHTML"' in form and 'hx-ext="morph"' in form


def test_every_name_holds_the_ticks_room_so_a_press_never_reflows_the_roster(ballot):
    def ticks(page):
        return [item.count("ballot-done__tick") for item in re.findall(r"<li.*?</li>", re.search(r'<ul class="ballot-done__roster">(.*?)</ul>', page, re.S)[0], re.S)]

    client = signed_in(ballot["ada"])
    before = ticks(client.get("/").text)
    post(client, "1")

    assert before == ticks(client.get("/").text) == [1] * len(ballot)
