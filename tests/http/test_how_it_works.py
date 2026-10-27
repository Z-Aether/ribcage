"""How it works: the permanent page and the name menu's first item (#134)."""

import re

import pytest

from ribcage.phase.order import PHASES, Phase
from tests.http.test_phase import walk_to

PAGE = "/how-it-works/"
# The entry each phase marks, and the one button under it (#134).
NOW = {
    Phase.SUGGEST: ("Suggest", "Suggest films"),
    Phase.APPROVE: ("Suggest", "See the suggestions"),
    Phase.VOTE: ("Vote", "Vote"),
    Phase.PICK: ("The evening", "See the scores"),
    Phase.RUN: ("The evening", "Follow the evening"),
}
ENTRIES = ["Suggest", "Vote", "The evening"]


@pytest.fixture
def ada(client, voters):
    client.force_login(voters["ada"])
    return client


def menu_links(page):
    menu = re.search(r"<details\b.*?</details>", page, re.S)[0]
    return re.findall(r'<a (?:class="[^"]+" )?href="([^"]+)"', menu)


@pytest.mark.parametrize("phase", PHASES)
def test_the_name_menu_lists_how_it_works_first_and_my_warnings_in_every_phase_but_run(ada, phase):
    walk_to(phase)

    links = menu_links(ada.get("/").text)

    assert links == (["/how-it-works/", "/password/"] if phase is Phase.RUN else ["/how-it-works/", "/warnings/", "/password/"])
    assert menu_links(ada.get(PAGE).text) == links


@pytest.mark.parametrize("phase", PHASES)
def test_the_page_lists_the_three_entries_and_marks_the_phases_one_now_with_its_button_under_it(ada, phase):
    walk_to(phase)
    page = ada.get(PAGE).text
    marked, button = NOW[phase]

    assert re.findall(r'<li class="how-entry[^"]*">\s*<h2>([^<]+?)\s*(?:<|</h2>)', page) == ENTRIES
    assert re.findall(r'<li class="how-entry is-now">\s*<h2>(.*?)</h2>', page, re.S) == [f'{marked} <span class="how-entry__now">now</span>']
    assert page.count("how-entry__now") == 1
    assert page.count('<li class="how-go"') == 1
    after_now = re.search(r'<li class="how-entry is-now">.*?</li>\s*<li class="how-go"[^>]*><a href="/" class="button">([^<]+)</a></li>', page, re.S)
    assert after_now and after_now[1] == button


@pytest.mark.parametrize("phase", PHASES)
def test_set_up_my_warnings_shows_in_every_phase_but_run(ada, phase):
    walk_to(phase)

    page = ada.get(PAGE).text

    assert ('<p class="how-go"><a href="/warnings/" class="button">Set up my warnings</a></p>' in page) is (phase is not Phase.RUN)


def test_the_page_is_the_same_whenever_it_is_visited_and_names_the_marathon(ada):
    def without_token(page):
        return re.sub(r'(?:csrfmiddlewaretoken" value=|X-CSRFToken": )"[^"]+"', "", page)

    first = without_token(ada.get(PAGE).text)

    assert without_token(ada.get(PAGE).text) == first
    assert "<h1>Welcome to Test Night</h1>" in first
    assert "Ribcage" not in first


def test_the_vote_entry_draws_the_ballots_marks_without_repeating_its_scores_sentence(ada):
    page = ada.get(PAGE).text

    assert "ballot-legend__mark--ring" in page and "ballot-legend__mark--seen" in page and "ballot-legend__mark--veto" in page
    assert 'class="ballot-legend__scores"' not in page


def test_a_voter_who_must_change_their_password_is_led_there_from_the_page(client, voters):
    ada = voters["ada"]
    ada.must_change_password = True
    ada.save()
    client.force_login(ada)

    assert client.get(PAGE).headers["Location"].startswith("/password/")


def test_the_page_is_behind_the_login_wall(client, db):
    assert client.get(PAGE).headers["Location"] == f"/login/?next={PAGE}"
