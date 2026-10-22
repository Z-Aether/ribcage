import re

import pytest
from django.templatetags.static import static

from ribcage.identity.models import Voter
from ribcage.identity.views import WELCOME_PENDING
from tests.http.routes import VOTER, as_a_page, pages_of, public_pages

TMDB_NOTICE = "This product uses the TMDB API but is not endorsed or certified by TMDB."
DTDD_CREDIT = '<a href="https://www.doesthedogdie.com/">Powered by DoesTheDogDie.com</a>'

PUBLIC_PAGES = [path for path, _ in public_pages()]
# Every fixed-address voter route, each held as a page if it answers GET; the gallery among them, which needs DEBUG on.
WALLED_PAGES = [path for path, _ in pages_of(VOTER)]


@pytest.fixture
def voter(db):
    return Voter.objects.create_voter("Ada")


@pytest.fixture
def client(client, voter, settings):
    settings.DEBUG = True
    client.force_login(voter)
    return client


def visit(client, path):
    # Welcome answers only a voter who has just registered (#75).
    session = client.session
    session[WELCOME_PENDING] = True
    session.save()
    return as_a_page(client.get(path))


def footer(page):
    return re.search(r"<footer\b.*?</footer>", page, re.S)[0]


def header(page):
    found = re.search(r"<header class=\"voter-header\".*?</header>", page, re.S)
    return found[0] if found else ""


def the_footers_four_parts(abuse_email):
    # TMDB's attribution is two of these: the logo and the notice (#5).
    return {
        "the TMDB logo": f'src="{static("vendor/tmdb/blue_short.svg")}"',
        "the TMDB notice": TMDB_NOTICE,
        "the DoesTheDogDie credit": DTDD_CREDIT,
        ABUSE_MAILTO: f'href="mailto:{abuse_email}"',
        "the privacy policy": '<a href="/privacy/">Privacy policy</a>',
    }


ABUSE_MAILTO = "the abuse mailto:"


def missing_from_the_footer(page, settings):
    shown = footer(page)
    return [part for part, html in the_footers_four_parts(settings.ABUSE_EMAIL).items() if html not in shown]


def test_some_walled_page_is_found():
    assert "/" in WALLED_PAGES


@pytest.mark.parametrize("path", WALLED_PAGES)
def test_every_walled_voter_page_has_the_footer(client, settings, path):
    response = visit(client, path)

    assert response.status_code == 200
    assert missing_from_the_footer(response.text, settings) == []


@pytest.mark.parametrize("path", WALLED_PAGES)
def test_every_walled_voter_page_has_the_header_naming_the_signed_in_voter(client, path):
    shown = header(visit(client, path).text)

    assert '<a class="wordmark voter-header__wordmark" href="/">Ribcage</a>' in shown
    assert re.search(r"<summary[^>]*>\s*Ada\s*</summary>", shown)


def test_the_header_names_whichever_voter_is_signed_in(client, db):
    client.force_login(Voter.objects.create_voter("Grete"))

    shown = header(client.get("/").text)

    assert "Grete" in shown
    assert "Ada" not in shown


def test_the_name_menu_holds_change_password_and_a_log_out_post_and_nothing_else(client):
    shown = header(client.get("/").text)
    menu = re.search(r"<details\b.*?</details>", shown, re.S)[0]

    assert re.findall(r'<a href="([^"]+)"', menu) == ["/password/"]
    assert re.search(r'<form method="post" action="/logout/">.*?<button[^>]*>Log out</button>', menu, re.S)
    assert len(re.findall(r"<li\b", menu)) == 2


def test_the_abuse_address_comes_from_its_setting(client, settings):
    settings.ABUSE_EMAIL = "someone@example.org"

    assert 'href="mailto:someone@example.org"' in footer(client.get("/").text)


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_every_public_page_has_the_footers_links_but_no_abuse_mailto_or_header_menu(client, settings, path):
    page = client.get(path).text

    assert missing_from_the_footer(page, settings) == [ABUSE_MAILTO]
    assert "mailto:" not in footer(page)
    assert "voter-header" not in page
    assert "<details" not in page
