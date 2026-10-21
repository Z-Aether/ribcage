import re

import pytest

from ribcage.identity.models import Voter
from ribcage.phase.history import move
from ribcage.phase.order import Phase
from tests.http.test_admin_login import sign_in_as_the_admin
from tests.http.test_phase import walk_to
from tests.http.test_voter_shell import missing_from_the_footer

SUGGEST, APPROVE, VOTE, PICK, RUN = Phase
TABS = {"Phase": "/console/phase/", "Films": "/console/films/", "Pick": "/console/pick/", "Roster": "/console/roster/"}


@pytest.fixture
def admin(client, db):
    sign_in_as_the_admin(client)
    return client


def header(page):
    return re.search(r'<header class="console-header">.*?</header>', page, re.S)[0]


def voter_side(page):
    line = re.search(r'<p class="console-header__voter-side">(.*?)</p>', header(page), re.S)[1]
    return re.sub(r"<[^>]+>", "", line)


def tabs(page):
    return re.findall(r'<a href="([^"]+)"( aria-current="page")?>([^<]+)</a>', re.search(r"<nav\b.*?</nav>", page, re.S)[0])


@pytest.mark.parametrize(("phase", "tab"), [(SUGGEST, "Films"), (APPROVE, "Films"), (VOTE, "Films"), (PICK, "Pick"), (RUN, "Pick")])
def test_the_console_opens_on_the_tab_for_the_phases_work(admin, phase, tab):
    walk_to(phase)

    response = admin.get("/console/")

    assert (response.status_code, response.headers["Location"]) == (302, TABS[tab])


@pytest.mark.parametrize("path", TABS.values())
def test_each_tab_stays_put_when_the_phase_moves(admin, path):
    before = admin.get(path)
    walk_to(RUN)
    move(RUN, PICK)

    assert before.status_code == admin.get(path).status_code == 200


@pytest.mark.parametrize(("label", "path"), TABS.items())
def test_every_tab_shows_the_four_tabs_in_order_marking_its_own(admin, label, path):
    shown = tabs(admin.get(path).text)

    assert [(href, name) for href, _, name in shown] == [(href, name) for name, href in TABS.items()]
    assert [name for _, current, name in shown if current] == [label]


@pytest.mark.parametrize("path", TABS.values())
def test_every_tab_wears_the_admin_skin_and_carries_the_footer(admin, settings, path):
    page = admin.get(path).text

    assert '<body data-skin="admin" ' in page
    assert missing_from_the_footer(page, settings) == []


def test_the_header_says_when_nobody_is_signed_in_on_the_voter_side(admin):
    assert voter_side(admin.get("/console/films/").text) == "Voter side ↗ · not signed in there"


def test_the_header_names_the_voter_signed_in_on_the_voter_side(admin):
    admin.force_login(Voter.objects.create_voter("Dani"))

    assert voter_side(admin.get("/console/films/").text) == "Voter side ↗ · signed in there as Dani"


def test_the_voter_side_links_to_the_phase_page_in_a_new_tab(admin):
    shown = header(admin.get("/console/films/").text)

    assert '<a href="/" target="_blank">Voter side ↗</a>' in shown


def test_the_header_ends_with_a_log_out_that_posts_to_the_admin_log_out(admin):
    shown = header(admin.get("/console/films/").text)

    assert re.search(r'<form method="post" action="/console/logout/">.*?<button[^>]*>Log out</button>\s*</form>\s*</div>\s*</header>', shown, re.S)


def test_the_wordmark_leads_back_to_the_console(admin):
    assert '<a class="wordmark console-header__wordmark" href="/console/">Ribcage</a>' in header(admin.get("/console/films/").text)
