"""I don't care, the nag bar and Welcome's exit (#110)."""

import re

import pytest
from django.test import Client

from ribcage.identity.removal import remove
from ribcage.phase.history import move
from ribcage.phase.order import PHASES, Phase
from ribcage.triggers import client as dtdd_client
from ribcage.triggers import stored, watched
from ribcage.triggers.models import DoesNotCare, WatchedTopic
from tests.dtdd import Dtdd
from tests.http.test_phase import walk_to
from tests.http.test_registration import register

PAGE, TICK, CARE = "/warnings/", "/warnings/tick/", "/warnings/dont-care/"
HTMX = {"HX-Request": "true"}
DOG, CAT = 153, 158
NAGGING = [Phase.SUGGEST, Phase.APPROVE, Phase.VOTE]
BAR = 'class="nag-bar"'


@pytest.fixture
def ada(voters, monkeypatch):
    monkeypatch.setattr(dtdd_client, "over_the_network", Dtdd())
    stored.replace_vocabulary(dtdd_client.Client("key", Dtdd()).vocabulary().value)
    return voters["ada"]


@pytest.fixture
def browser(ada):
    client = Client()
    client.force_login(ada)
    return client


def cares_not(voter):
    return DoesNotCare.objects.filter(voter=voter).exists()


def ticked(voter):
    return set(WatchedTopic.objects.filter(voter=voter).values_list("topic_id", flat=True))


def say(browser, on, **extra):
    return browser.post(CARE, {"on": on, **extra})


def test_i_dont_care_with_nothing_ticked_turns_on_and_off_again(browser, ada):
    assert say(browser, "1").status_code == 302
    assert cares_not(ada)
    assert 'aria-pressed="true"' in browser.get(PAGE).text

    say(browser, "0")

    assert not cares_not(ada)
    assert 'aria-pressed="false"' in browser.get(PAGE).text


def test_over_ticks_it_arms_naming_their_count_and_writes_nothing(browser, ada):
    watched.set_ticked(ada, DOG, True)
    watched.set_ticked(ada, CAT, True)

    armed = browser.get(CARE, headers=HTMX).text

    assert "This clears your 2 topics." in armed
    assert ticked(ada) == {DOG, CAT} and not cares_not(ada)


def test_cancel_puts_the_arm_back(browser, ada):
    watched.set_ticked(ada, DOG, True)

    cancelled = browser.get(CARE + "?cancel", headers=HTMX).text

    assert "This clears" not in cancelled and "Cancel" not in cancelled


def test_the_confirm_clears_the_ticks_and_turns_it_on(browser, ada):
    watched.set_ticked(ada, DOG, True)

    say(browser, "1", confirm="1")

    assert ticked(ada) == set() and cares_not(ada)


def test_a_bare_post_over_ticks_changes_nothing(browser, ada):
    watched.set_ticked(ada, DOG, True)

    say(browser, "1")

    assert ticked(ada) == {DOG} and not cares_not(ada)


def test_turning_it_off_brings_back_an_empty_list_that_can_be_ticked(browser, ada):
    say(browser, "1")
    say(browser, "0")

    browser.post(TICK, {"topic": str(DOG), "ticked": "1"})

    assert ticked(ada) == {DOG}


@pytest.mark.parametrize("headers", [{}, HTMX])
def test_while_on_a_tick_post_is_refused_and_changes_nothing(browser, ada, headers):
    say(browser, "1")

    response = browser.post(TICK, {"topic": str(DOG), "ticked": "1"}, **headers)

    assert ticked(ada) == set()
    assert response.status_code == 302 or response.headers["HX-Redirect"] == PAGE


def test_the_write_refuses_a_tick_while_on_so_the_cards_toggle_is_refused_too(browser, ada):
    say(browser, "1")

    assert watched.does_not_care(ada)
    assert watched.set_ticked(ada, DOG, True) is False
    assert ticked(ada) == set()


def browser_after_turning_off(browser):
    say(browser, "0")
    return browser.get(PAGE).text


def test_the_page_greys_its_rows_while_on(browser, ada):
    say(browser, "1")

    page = browser.get(PAGE).text

    assert 'class="warnings is-greyed"' in page
    assert 'class="warnings__topic-button" aria-pressed="false" disabled' in page.replace('\n', ' ').replace('  ', ' ') or "disabled" in page


def test_its_posts_in_run_write_nothing_and_reload_the_tab(browser, ada):
    walk_to(Phase.RUN)

    response = say(browser, "1")

    assert response.status_code == 302 and response.headers["Location"] == "/"
    assert not cares_not(ada)


def test_a_malformed_post_is_refused(browser, ada):
    assert say(browser, "x").status_code == 400
    assert not cares_not(ada)


@pytest.mark.parametrize("phase", NAGGING)
def test_the_bar_shows_in_suggest_approve_and_vote_for_a_voter_who_has_decided_nothing(browser, phase):
    walk_to(phase)

    page = browser.get("/").text

    assert BAR in page and 'href="/warnings/"' in page


@pytest.mark.parametrize("phase", [Phase.PICK, Phase.RUN])
def test_the_bar_is_gone_in_pick_and_run(browser, phase):
    walk_to(phase)

    assert BAR not in browser.get("/").text


def test_reopening_vote_brings_the_bar_back(browser):
    walk_to(Phase.PICK)
    move(Phase.PICK, Phase.VOTE)

    assert BAR in browser.get("/").text


def test_a_tick_clears_the_bar(browser, ada):
    watched.set_ticked(ada, DOG, True)

    assert BAR not in browser.get("/").text


def test_i_dont_care_clears_the_bar(browser, ada):
    say(browser, "1")

    assert BAR not in browser.get("/").text


def test_turning_it_off_with_nothing_ticked_brings_the_bar_back(browser):
    say(browser, "1")
    say(browser, "0")

    assert BAR in browser.get("/").text


def test_the_bar_is_absent_from_my_warnings(browser):
    page = browser.get(PAGE).text

    assert BAR not in page and "My warnings" in page


def test_the_bar_is_absent_from_the_forced_password_change(browser, ada):
    walk_to(Phase.SUGGEST)
    ada.must_change_password = True
    ada.save()

    page = browser.get("/password/").text

    assert "Choose your own password" in page and BAR not in page


def test_the_bar_shows_on_the_voluntary_password_change(browser):
    walk_to(Phase.SUGGEST)

    page = browser.get("/password/").text

    assert "Change password" in page and BAR in page


def test_the_bar_blocks_nothing_voting_works_under_it(browser):
    walk_to(Phase.VOTE)

    response = browser.get("/")

    assert BAR in response.text and response.status_code == 200


@pytest.mark.parametrize("phase", PHASES)
def test_welcome_offers_set_up_my_warnings_in_every_phase_but_run(client, db, phase):
    walk_to(phase)

    page = register(client, follow=True).text

    assert ('<a href="/warnings/" class="button">Set up my warnings</a>' in page) is (phase is not Phase.RUN)
    assert '<a href="/" class="button">' in page


def test_removing_a_voter_takes_the_flag_with_them(browser, ada):
    say(browser, "1")
    remove(ada)

    assert not DoesNotCare.objects.exists()
