"""My warnings: the page, ticking, and the watched list it keeps (#107)."""

import html
import re

import pytest
from django.conf import settings
from django.test import Client

from ribcage.identity.removal import remove
from ribcage.phase.order import PHASES, Phase
from ribcage.triggers import client as dtdd_client
from ribcage.triggers import stored, watched
from ribcage.triggers.models import Topic, WatchedTopic
from tests.dtdd import VOCABULARY, Dtdd
from tests.http.routes import VOTER, route_templates, routes_of
from tests.http.test_phase import walk_to
from tests.http.test_roster_tab import TAB, confirm

PAGE, TICK = "/warnings/", "/warnings/tick/"
HTMX = {"HX-Request": "true"}
DOG, CAT, JUMP = 153, 158, 200
WRITING = [Phase.SUGGEST, Phase.APPROVE, Phase.VOTE, Phase.PICK]


@pytest.fixture
def dtdd(monkeypatch):
    def install(transport):
        monkeypatch.setattr(dtdd_client, "over_the_network", transport)
        return transport

    return install


@pytest.fixture
def vocabulary(dtdd):
    """The three-topic vocabulary, stored: Animals holds cat death and dog death, Scary stuff holds jump scares."""
    stored.replace_vocabulary(dtdd_client.Client("key", Dtdd()).vocabulary().value)


@pytest.fixture
def ada(voters, vocabulary):
    return voters["ada"]


@pytest.fixture
def browser(ada):
    client = Client()
    client.force_login(ada)
    return client


def ticked(voter):
    return set(WatchedTopic.objects.filter(voter=voter).values_list("topic_id", flat=True))


def tick(browser, topic, ticked=True, **extra):
    return browser.post(TICK, {"topic": str(topic), "ticked": "1" if ticked else "0"}, **extra)


def sections(page):
    found = re.findall(r'<details class="warnings__section" id="([^"]+)"( open)?>(.*?)</details>', page, re.S)
    return {
        anchor: {
            "open": bool(opened),
            "count": html.unescape(re.search(r'class="warnings__count"[^>]*>([^<]+)<', body)[1]),
            "labels": [re.sub(r"\s+", " ", label).strip() for label in re.findall(r"</span>\s*([^<]+?)\s*</button>", body)],
        }
        for anchor, opened, body in found
    }


def chips(page):
    return [html.unescape(label) for label in re.findall(r'class="warnings__chip-button" title="Remove ([^"]+)"', page)]


def test_the_page_groups_topics_as_does_the_dog_die_does_collapsed_with_counts_and_alphabetical_rows(browser):
    page = browser.get(PAGE).text

    found = sections(page)
    assert list(found) == ["group-54", "group-50"]
    assert found["group-54"] == {"open": False, "count": "2 topics", "labels": ["cat death", "dog death"]}
    assert found["group-50"]["labels"] == ["jump scares"]
    assert "Powered by DoesTheDogDie.com" in page.split("warnings__credit")[1]
    assert "Only you see this list" in page and "torn down" in page
    assert 'title="A dog dies."' in page


def test_a_section_header_counts_its_ticked_topics_and_the_chips_list_them_alphabetically(browser, ada):
    watched.set_ticked(ada, JUMP, True)
    watched.set_ticked(ada, DOG, True)
    watched.set_ticked(ada, 99999, True)

    page = browser.get(PAGE).text

    assert sections(page)["group-54"]["count"] == "2 topics · 1 ticked"
    assert chips(page) == ["dog death", "jump scares"]


def test_ticking_stores_the_topic_id_posted_in_the_body_and_unticking_removes_it(browser, ada):
    tick(browser, DOG)
    tick(browser, DOG)
    tick(browser, CAT)
    assert ticked(ada) == {DOG, CAT}

    tick(browser, DOG, ticked=False)
    tick(browser, DOG, ticked=False)

    assert ticked(ada) == {CAT}


def test_a_list_is_one_voters_own(browser, ada, voters):
    tick(browser, DOG)

    assert ticked(voters["Hanna"]) == set() and ticked(ada) == {DOG}


def test_an_htmx_tick_swaps_in_the_row_the_count_and_the_chips_by_id(browser):
    response = tick(browser, DOG, headers=HTMX)

    body = response.text
    assert response.status_code == 200
    assert re.search(r'<li id="topic-153" class="warnings__topic is-ticked" hx-swap-oob="morph"[^>]*>', body)
    assert 'id="group-54-count"' in body and "2 topics · 1 ticked" in html.unescape(body)
    assert 'id="warnings-chips"' in body and chips(body) == ["dog death"]
    assert 'name="ticked" value="0"' in body


def test_unticking_from_a_chip_is_the_same_post(browser, ada):
    tick(browser, DOG)
    page = browser.get(PAGE).text
    chip = re.search(r'<form class="warnings__chip".*?</form>', page, re.S)[0]

    assert 'name="topic" value="153"' in chip and 'name="ticked" value="0"' in chip
    tick(browser, DOG, ticked=False, headers=HTMX)
    assert ticked(ada) == set()


def test_a_plain_post_reloads_the_page_at_the_section_it_was_made_in_with_that_section_open_once(browser):
    response = tick(browser, JUMP)

    assert response.status_code == 302 and response.headers["Location"] == "/warnings/#group-50"
    found = sections(browser.get(PAGE).text)
    assert found["group-50"]["open"] and not found["group-54"]["open"]
    assert not sections(browser.get(PAGE).text)["group-50"]["open"]


@pytest.mark.parametrize(
    "body",
    [{}, {"topic": "x", "ticked": "1"}, {"topic": "-1", "ticked": "1"}, {"topic": "0", "ticked": "1"}, {"topic": str(2**40), "ticked": "1"}, {"topic": "153"}, {"topic": "153", "ticked": "yes"}],
)
def test_a_malformed_post_is_refused_and_writes_nothing(browser, ada, body):
    assert browser.post(TICK, body).status_code == 400
    assert ticked(ada) == set()


@pytest.mark.parametrize("phase", PHASES)
def test_a_post_writes_in_every_phase_but_run_and_there_reloads_the_tab(browser, ada, phase):
    walk_to(phase)

    response = tick(browser, DOG, headers=HTMX)

    if phase in WRITING:
        assert ticked(ada) == {DOG}
    else:
        assert ticked(ada) == set()
        assert response.headers["HX-Redirect"] == "/"
        assert tick(browser, DOG).headers["Location"] == "/"


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_the_write_answers_405_to_any_other_method_and_the_page_to_a_post(browser, method):
    assert getattr(browser, method)(TICK).status_code == 405
    assert browser.get(TICK, {"topic": "153", "ticked": "1"}).status_code == 405
    assert browser.post(PAGE, {"topic": "153"}).status_code == 405


@pytest.mark.parametrize("phase", PHASES)
def test_the_menu_link_shows_in_every_phase_but_run_first_in_the_name_menu_and_not_beside_it(browser, phase):
    walk_to(phase)

    page = browser.get("/").text
    header = re.search(r"<header class=\"voter-header\".*?</header>", page, re.S)[0]
    menu = re.search(r"<details.*?</details>", header, re.S)[0]

    assert ('href="/warnings/"' in menu) is (phase is not Phase.RUN)
    assert header.count('href="/warnings/"') == menu.count('href="/warnings/"')
    if phase is not Phase.RUN:
        assert re.findall(r'<a href="([^"]+)"', menu)[:2] == ["/warnings/", "/password/"]


def test_the_page_in_run_redirects_to_the_phase_page(browser):
    walk_to(Phase.RUN)

    response = browser.get(PAGE)

    assert response.status_code == 302 and response.headers["Location"] == "/"


def test_the_page_needs_a_voter(client, db):
    assert client.get(PAGE).headers["Location"].startswith("/login/")
    assert client.post(TICK).headers["Location"].startswith("/login/")


def test_removing_a_voter_deletes_their_list_and_the_rosters_confirm_says_nothing_of_it(admin, voters, vocabulary):
    watched.set_ticked(voters["ada"], DOG, True)
    watched.set_ticked(voters["Hanna"], DOG, True)
    page = admin.get(TAB, {"remove": voters["ada"].pk}).text
    armed = confirm(page)

    ada_pk = voters["ada"].pk
    remove(voters["ada"])

    assert armed is not None
    said = armed[-1].lower()
    assert "warning" not in said and "watched" not in said and "topic" not in said
    assert ticked(voters["Hanna"]) == {DOG} and not WatchedTopic.objects.filter(voter_id=ada_pk).exists() and WatchedTopic.objects.count() == 1


def test_the_admin_sees_nobodys_list_on_the_console(admin, voters, vocabulary):
    watched.set_ticked(voters["ada"], JUMP, True)

    for tab in ["/console/", "/console/phase/", "/console/films/", "/console/pick/", "/console/roster/"]:
        page = admin.get(tab, follow=True).text
        assert "jump scares" not in page and "warnings__" not in page


def test_no_voter_route_names_a_topic_in_its_address(browser, ada):
    # Every route is a fixed path, so a topic or search text could only come in as a converter or a query (#16, #107).
    assert [template for template, entry in route_templates() if "<" in template] == []
    tick(browser, DOG)
    page = browser.get(PAGE).text
    addresses = re.findall(r'(?:href|action|hx-post|hx-get)="([^"]+)"', page)

    assert TICK in addresses
    assert [address for address in addresses if "?" in address or "153" in address or "dog%20death" in address or "dog+death" in address or "dog death" in address] == []
    assert {entry.name for _, entry in routes_of(VOTER)} >= {"warnings", "warnings_tick"}


def test_with_no_vocabulary_the_page_fetches_it(ada, dtdd):
    Topic.objects.all().delete()
    transport = dtdd(Dtdd())
    browser = Client()
    browser.force_login(ada)
    watched.set_ticked(ada, DOG, True)

    page = browser.get(PAGE).text

    assert transport.paths and Topic.objects.count() == len(VOCABULARY["/topics"])
    assert chips(page) == ["dog death"]


def test_with_does_the_dog_die_not_answering_the_page_says_so_and_keeps_the_list(ada, dtdd):
    Topic.objects.all().delete()
    dtdd(Dtdd(error=ConnectionError("down")))
    browser = Client()
    browser.force_login(ada)
    watched.set_ticked(ada, DOG, True)

    page = browser.get(PAGE).text

    assert "can't be shown yet" in html.unescape(page) and "Try again in a bit" in page
    assert "warnings__section" not in page and "153" not in page and "Powered by DoesTheDogDie.com" in page
    assert ticked(ada) == {DOG}


def test_the_page_in_run_fetches_nothing(ada, dtdd):
    Topic.objects.all().delete()
    transport = dtdd(Dtdd())
    walk_to(Phase.RUN)
    browser = Client()
    browser.force_login(ada)

    browser.get(PAGE)

    assert transport.paths == []


def test_a_retired_topic_stays_stored_and_never_shows(browser, ada):
    watched.set_ticked(ada, 99999, True)

    page = browser.get(PAGE).text

    assert chips(page) == [] and "99999" not in page and ticked(ada) == {99999}


def test_the_page_loads_the_script_that_holds_the_clicked_row_still(browser):
    # A tick resizes the chips box above the rows; the script keeps the clicked row where it was (#107).
    assert "/static/warnings/holds-the-row." in browser.get(PAGE).text


SEARCH_SCRIPT = (settings.BASE_DIR / "ribcage" / "static" / "warnings" / "search.js").read_text()


def test_the_search_box_is_hidden_until_its_script_runs_and_sits_in_no_form(browser):
    page = browser.get(PAGE).text

    box = re.search(r'<div class="warnings__search" data-warnings-search hidden>.*?</div>', page, re.S)[0]
    assert "<input" in box and "<form" not in box
    forms = re.findall(r"<form.*?</form>", page, re.S)
    assert forms and all("warnings__search-box" not in form for form in forms)
    assert "data-warnings-no-match hidden" in page
    assert "/static/warnings/search." in page


def test_searching_can_not_make_a_request_its_script_fetches_nothing_and_the_box_has_no_name(browser):
    page = browser.get(PAGE).text

    assert "name=" not in re.search(r'<input type="search"[^>]*>', page)[0]
    for call in ("fetch", "XMLHttpRequest", "sendBeacon", "htmx.", "location", "history", "submit", "WebSocket", "Image("):
        assert call not in SEARCH_SCRIPT


def test_every_row_carries_its_label_and_keywords_for_the_search_to_match(browser):
    page = browser.get(PAGE).text

    assert re.search(r'<li id="topic-153"[^>]*data-search="dog death dog"', page)
    assert re.search(r'<li id="topic-200"[^>]*data-search="jump scares "', page)
    assert 'data-search="dog death dog"' in tick(browser, DOG, headers=HTMX).text
