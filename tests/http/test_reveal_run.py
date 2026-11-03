"""The reveal behind the evening: its own address in RUN, one header link from the evening (#27, #161)."""

import re

import pytest
from django.urls import reverse

from ribcage.ballot.models import BallotRecord
from ribcage.phase.order import Phase
from tests.http.test_ballot_page import film
from tests.http.test_matched_topics import signed_in
from tests.http.test_phase import walk_to

REVEAL = "/reveal/"
SCORES = "Everyone's scores"
EVENING = "← The evening"


def mark(voter, suggestion, **fields):
    BallotRecord.objects.create(voter=voter, suggestion=suggestion, **fields)


def titles_down(page):
    return re.findall(r'<span class="reveal__title-line">([^<]*?)(?: <span|</span>)', page)


def header_of(page):
    return re.search(r'<header class="voter-header">.*?</header>', page, re.S)[0]


def test_the_address_is_the_reveal_page_route():
    assert reverse("reveal_page") == REVEAL


def test_in_run_the_evening_links_to_the_reveal_and_the_reveal_links_back(voters):
    walk_to(Phase.RUN)
    client = signed_in(voters["ada"])

    evening = client.get("/").text
    reveal = client.get(REVEAL).text

    assert f'href="{REVEAL}">{SCORES}</a>' in header_of(evening) and EVENING not in header_of(evening)
    assert f'href="/">{EVENING}</a>' in header_of(reveal) and SCORES not in header_of(reveal)


def test_the_reveal_in_run_wears_the_voter_skin_and_does_not_poll(voters):
    walk_to(Phase.RUN)

    page = signed_in(voters["ada"]).get(REVEAL).text

    assert 'data-skin="voter"' in page and "hx-trigger" not in page and 'id="evening"' not in page


def test_the_reveal_in_run_is_the_same_matrix_and_sorts(voters):
    walk_to(Phase.PICK)
    one, two = film(voters["Hanna"], "One"), film(voters["Hanna"], "Two")
    mark(voters["ada"], one, score=1)
    mark(voters["ada"], two, score=3)
    walk_to_run_from_pick()
    client = signed_in(voters["ada"])

    by_points = client.get(REVEAL).text
    by_film = client.get(REVEAL, {"sort": "film"}).text

    assert titles_down(by_points) == ["Two", "One"]
    assert titles_down(by_film) == ["One", "Two"]
    assert 'data-sort="film"' in by_film and 'href="?sort=' in by_film


def walk_to_run_from_pick():
    from ribcage.phase.history import move

    move(Phase.PICK, Phase.RUN)


def test_a_dropped_film_is_absent_from_the_reveal_in_run(voters):
    from ribcage.suggestions.models import Approval

    walk_to(Phase.PICK)
    film(voters["Hanna"], "Kept")
    dropped = film(voters["Hanna"], "Dropped", Approval.DROPPED)
    walk_to_run_from_pick()

    page = signed_in(voters["ada"]).get(REVEAL).text

    assert titles_down(page) == ["Kept"] and f'data-suggestion="{dropped.pk}"' not in page


def test_its_card_opens_with_no_trigger_content_and_no_credit(voters):
    walk_to(Phase.PICK)
    one = film(voters["Hanna"], "One")
    mark(voters["ada"], one, score=2)
    walk_to_run_from_pick()
    client = signed_in(voters["ada"])
    page = client.get(REVEAL).text

    card = client.get(reverse("reveal_card"), {"suggestion": one.pk}, headers={"HX-Request": "true"}).text

    assert "data-card-at" in page
    assert "reveal__detail" in card and "data-dtdd" not in card and "DoesTheDogDie" not in card


def test_in_pick_the_address_redirects_to_the_reveal_at_the_root(voters):
    walk_to(Phase.PICK)

    response = signed_in(voters["ada"]).get(REVEAL)

    assert response.status_code == 302 and response["Location"] == "/"


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE, Phase.VOTE])
def test_before_the_reveal_the_address_reloads_into_the_phase_and_shows_no_score(voters, phase):
    walk_to(phase)
    client = signed_in(voters["ada"])

    plain = client.get(REVEAL)
    htmx = client.get(REVEAL, headers={"HX-Request": "true"})

    assert plain.status_code == 302 and plain["Location"] == "/"
    assert htmx["HX-Redirect"] == "/" and b"reveal" not in htmx.content.lower()


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE, Phase.VOTE, Phase.PICK])
def test_no_link_between_the_evening_and_the_reveal_shows_outside_run(voters, phase):
    walk_to(phase)

    page = signed_in(voters["ada"]).get("/").text

    assert SCORES not in header_of(page) and EVENING not in header_of(page)


def test_in_run_the_other_pages_carry_neither_link(voters):
    walk_to(Phase.RUN)
    client = signed_in(voters["ada"])

    for address in ("/how-it-works/", "/password/"):
        text = client.get(address).text
        assert SCORES not in header_of(text) and EVENING not in header_of(text)


def test_an_anonymous_visitor_is_sent_to_log_in(db):
    from django.test import Client

    assert Client().get(REVEAL)["Location"].startswith("/login/")


def test_the_reveal_in_run_has_the_shell_the_voter_pages_do(voters):
    walk_to(Phase.RUN)

    page = signed_in(voters["ada"]).get(REVEAL).text

    assert re.search(r"<summary[^>]*>\s*ada\s*</summary>", header_of(page), re.I) and '<footer class="site-footer">' in page
