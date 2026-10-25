"""The viewer's matched topics and the ring on the pool's cards, by their own watched list, and never on the Films tab (#35 §2, #111)."""

import re
from datetime import UTC, datetime

import pytest
from django.test import Client

from ribcage.phase.order import Phase
from ribcage.suggestions.models import Suggestion
from ribcage.triggers import correction, stored, watched
from ribcage.triggers.dtdd import Record, Snapshot, TopicCount
from tests.http.test_my_warnings import CAT, DOG, JUMP, dtdd, vocabulary  # noqa: F401
from tests.http.test_phase import walk_to

AT = datetime(2026, 10, 25, tzinfo=UTC)
RING = "has-trigger-icon"
NOTE = "/note/"


def add(voter, title, **votes):
    suggestion = Suggestion.objects.create(title=title, suggester=voter, suggester_name=voter.display_name, runtime=100)
    counts = tuple(TopicCount({"dog": DOG, "cat": CAT, "jump": JUMP}[name], yes, no) for name, (yes, no) in votes.items())
    stored.store_lookup(suggestion, Snapshot(Record(suggestion.pk, title, 2000, "Movie"), counts), AT)
    return suggestion


def signed_in(voter):
    client = Client()
    client.force_login(voter)
    return client


def card(page, suggestion):
    return re.search(rf'<article class="film-card[^"]*" data-film-card data-suggestion="{suggestion.pk}".*?</article>', page, re.S)[0]


def ringed(page, suggestion):
    return RING in re.search(r'<div class="film-card__poster[^"]*"', card(page, suggestion))[0]


def matched_rows(page, suggestion):
    block = re.search(r'<div class="dtdd__matched">.*?</ul>', card(page, suggestion), re.S)
    return None if block is None else re.findall(r'dtdd__label">([^<]+)</span> — <span class="dtdd__counts">([^<]+)<', block[0])


@pytest.fixture
def pool(voters, vocabulary):  # noqa: F811
    ada, hanna = voters["ada"], voters["Hanna"]
    films = {
        "heavy": add(hanna, "Heavy", dog=(12, 1), cat=(2, 0)),
        "thin": add(hanna, "Thin", dog=(1, 0)),
        "contested": add(hanna, "Contested", dog=(5, 5)),
        "other": add(hanna, "Other", jump=(30, 0)),
    }
    watched.set_ticked(ada, DOG, True)
    watched.set_ticked(voters["Dani"], JUMP, True)
    return films


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE])
def test_the_ring_and_matched_block_follow_the_viewers_own_list(voters, pool, phase):
    walk_to(phase)
    page = signed_in(voters["ada"]).get("/").text

    assert [ringed(page, pool[key]) for key in ("heavy", "thin", "contested", "other")] == [True, False, False, False]
    assert matched_rows(page, pool["heavy"]) == [("dog death", "12 yes / 1 no")]
    # A thin or contested match is listed all the same, with no threshold (#20 §4).
    assert matched_rows(page, pool["thin"]) == [("dog death", "1 yes / 0 no")]
    assert matched_rows(page, pool["contested"]) == [("dog death", "5 yes / 5 no")]
    assert matched_rows(page, pool["other"]) is None


def test_another_voter_sees_their_own_ring_on_the_same_pool(voters, pool):
    page = signed_in(voters["Dani"]).get("/").text

    assert [ringed(page, pool[key]) for key in ("heavy", "other")] == [False, True]
    assert matched_rows(page, pool["other"]) == [("jump scares", "30 yes / 0 no")]
    assert matched_rows(page, pool["heavy"]) is None


def test_a_voter_with_nothing_ticked_sees_neither(voters, pool):
    page = signed_in(voters["Hanna"]).get("/").text

    assert RING not in page
    assert "dtdd__matched" not in page


def test_a_voter_who_does_not_care_sees_neither(voters, pool):
    watched.stop_caring(voters["ada"])
    page = signed_in(voters["ada"]).get("/").text

    assert RING not in page
    assert "dtdd__matched" not in page


def test_the_card_a_note_swaps_in_keeps_its_ring_and_matched_block(voters, pool):
    walk_to(Phase.SUGGEST)
    page = signed_in(voters["ada"]).post(NOTE, {"suggestion": pool["heavy"].pk, "text": "Sounds great"}, headers={"HX-Request": "true"}).text

    assert RING in page
    assert matched_rows(page, pool["heavy"]) == [("dog death", "12 yes / 1 no")]


def corrected_to(client, suggestion, **votes):
    counts = tuple(TopicCount({"dog": DOG, "cat": CAT, "jump": JUMP}[name], yes, no) for name, (yes, no) in votes.items())
    signed = correction.signed(Snapshot(Record(999, "Right one", 2000, "Movie"), counts), suggestion.pk)
    return client.post("/dtdd/match/", {"suggestion": suggestion.pk, "snapshot": signed}, headers={"HX-Request": "true"}).text


def poster_out_of_band(page):
    return re.search(r'<div class="film-card__poster[^"]*"[^>]*hx-swap-oob="outerHTML"', page)[0]


def test_correcting_a_ringed_films_match_to_a_record_without_the_topic_takes_the_ring_away(voters, pool):
    walk_to(Phase.SUGGEST)
    page = corrected_to(signed_in(voters["ada"]), pool["heavy"], jump=(3, 0))

    assert RING not in poster_out_of_band(page)
    assert "dtdd__matched" not in page


def test_correcting_an_unringed_films_match_to_a_record_with_the_topic_puts_the_ring_on(voters, pool):
    walk_to(Phase.SUGGEST)
    page = corrected_to(signed_in(voters["ada"]), pool["other"], dog=(12, 1))

    assert RING in poster_out_of_band(page)
    assert id_of(page) == f"film-card-poster-{pool['other'].pk}"


def id_of(page):
    return re.search(r'<div class="film-card__poster[^>]*id="([^"]+)"', page)[1]


def test_the_films_tab_card_has_neither_even_with_a_voter_signed_in_on_the_same_browser(admin, voters, pool):
    page = admin.get("/console/films/").text

    assert RING not in page
    assert "dtdd__matched" not in page
