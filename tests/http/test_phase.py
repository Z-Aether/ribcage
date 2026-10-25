import re
from datetime import timedelta

import pytest
from django.utils import timezone

from ribcage.identity.models import Voter
from ribcage.phase.history import current, last_entered, move, reveal_has_happened
from ribcage.phase.models import PhaseMove
from ribcage.phase.order import PHASES, MoveRefused, Phase, neighbours

SUGGEST, APPROVE, VOTE, PICK, RUN = Phase
PAGE_HEADINGS = {
    SUGGEST: "Suggest films",
    APPROVE: "Suggestions are closed",
    VOTE: "Vote",
    PICK: "Voting is closed",
    RUN: "The evening",
}


def history():
    return list(PhaseMove.objects.values_list("phase", flat=True))


def walk_to(phase):
    for before, after in zip(PHASES, PHASES[1 : PHASES.index(phase) + 1]):
        move(before, after)


def test_a_fresh_database_is_in_suggest_with_no_history(db):
    assert current() is SUGGEST
    assert history() == []


def test_a_move_appends_the_phase_entered_and_when(db):
    before = timezone.now()

    move(SUGGEST, APPROVE)

    entry = PhaseMove.objects.get()
    assert (entry.phase, current()) == (APPROVE, APPROVE)
    assert before <= entry.at <= timezone.now()


def test_moves_forward_then_back_are_each_appended_and_the_newest_decides(db):
    walk_to(PICK)
    move(PICK, VOTE)

    assert history() == [APPROVE, VOTE, PICK, VOTE]
    assert current() is VOTE


def test_the_newest_move_decides_even_when_its_clock_reads_earlier(db):
    move(SUGGEST, APPROVE)
    move(APPROVE, VOTE)
    PhaseMove.objects.filter(phase=VOTE).update(at=timezone.now() - timedelta(days=30))

    assert current() is VOTE


@pytest.mark.parametrize("stale", [SUGGEST, VOTE, PICK])
def test_a_move_from_a_phase_that_is_not_current_is_refused_and_appends_nothing(db, stale):
    move(SUGGEST, APPROVE)

    with pytest.raises(MoveRefused):
        move(stale, PHASES[PHASES.index(stale) + 1])

    assert history() == [APPROVE]


def test_a_stale_caller_repeating_a_move_already_made_is_refused(db):
    move(SUGGEST, APPROVE)

    with pytest.raises(MoveRefused):
        move(SUGGEST, APPROVE)

    assert history() == [APPROVE]


@pytest.mark.parametrize("to_phase", [VOTE, RUN, SUGGEST, "SETUP"])
def test_a_move_more_than_one_step_is_refused_and_appends_nothing(db, to_phase):
    with pytest.raises(MoveRefused):
        move(SUGGEST, to_phase)

    assert history() == []


def test_with_no_history_no_phase_has_been_entered(db):
    assert last_entered() == {}


def test_each_phase_was_last_entered_at_its_newest_move(db, clock):
    entered = {}
    for before, after in [(SUGGEST, APPROVE), (APPROVE, VOTE), (VOTE, PICK), (PICK, VOTE), (VOTE, APPROVE)]:
        clock.advance(days=1)
        move(before, after)
        entered[after] = clock.now

    assert last_entered() == {APPROVE: entered[APPROVE], VOTE: entered[VOTE], PICK: entered[PICK]}
    assert [type(phase) for phase in last_entered()] == [Phase] * 3


def test_a_phase_is_last_entered_at_its_newest_move_even_when_its_clock_reads_earlier(db):
    walk_to(VOTE)
    move(VOTE, APPROVE)
    newest = PhaseMove.objects.filter(phase=APPROVE).last()
    PhaseMove.objects.filter(pk=newest.pk).update(at=timezone.now() - timedelta(days=30))

    assert last_entered()[APPROVE] == PhaseMove.objects.get(pk=newest.pk).at


@pytest.fixture
def voter_client(client, db):
    client.force_login(Voter.objects.create_voter("Ada"))
    return client


def heading(page):
    return re.search(r"<h1>(.*?)</h1>", page)[1]


def skin(page):
    return re.search(r'<body data-skin="([a-z]+)"', page)[1]


@pytest.mark.parametrize("phase", PHASES)
def test_the_phase_page_shows_the_page_of_the_phase_walked_forward_to(voter_client, phase):
    walk_to(phase)

    response = voter_client.get("/")

    assert response.status_code == 200
    assert heading(response.text) == PAGE_HEADINGS[phase]


@pytest.mark.parametrize("phase", PHASES[:-1])
def test_the_phase_page_shows_the_page_of_the_phase_walked_back_to(voter_client, phase):
    walk_to(RUN)
    while current() is not phase:
        move(current(), neighbours(current()).back)

    assert history()[-1] == phase
    assert heading(voter_client.get("/").text) == PAGE_HEADINGS[phase]


def test_the_phase_page_follows_a_move_forward_then_a_move_back(voter_client):
    move(SUGGEST, APPROVE)
    assert heading(voter_client.get("/").text) == PAGE_HEADINGS[APPROVE]

    move(APPROVE, SUGGEST)
    assert heading(voter_client.get("/").text) == PAGE_HEADINGS[SUGGEST]


@pytest.mark.parametrize("phase", PHASES)
def test_run_alone_wears_the_run_skin(voter_client, phase):
    walk_to(phase)

    assert skin(voter_client.get("/").text) == ("run" if phase is RUN else "voter")


@pytest.mark.parametrize("phase", PHASES)
def test_every_phase_page_sits_in_the_voter_shell(voter_client, phase):
    walk_to(phase)
    page = voter_client.get("/").text

    assert '<header class="voter-header">' in page
    assert "<footer" in page


@pytest.mark.parametrize(
    ("steps", "happened"),
    [
        ([], False),
        ([(SUGGEST, APPROVE), (APPROVE, VOTE)], False),
        ([(SUGGEST, APPROVE), (APPROVE, VOTE), (VOTE, PICK)], True),
        ([(SUGGEST, APPROVE), (APPROVE, VOTE), (VOTE, PICK), (PICK, VOTE)], True),
        ([(SUGGEST, APPROVE), (APPROVE, VOTE), (VOTE, APPROVE), (APPROVE, VOTE)], False),
    ],
)
def test_the_reveal_has_happened_once_the_history_holds_a_move_into_pick(db, steps, happened):
    for before, after in steps:
        move(before, after)

    assert reveal_has_happened() is happened
