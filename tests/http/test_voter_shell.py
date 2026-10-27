import re

import pytest
from django.templatetags.static import static
from django.test import Client

from ribcage.identity.models import Voter
from tests.http.routes import VOTER, as_a_page, pages_of, public_pages

TMDB_NOTICE = "This product uses the TMDB API but is not endorsed or certified by TMDB."
DTDD_CREDIT = '<a href="https://www.doesthedogdie.com/">Powered by DoesTheDogDie.com</a>'

PUBLIC_PAGES = [path for path, _ in public_pages()]
# Every fixed-address voter route, each held as a page if it answers GET; the gallery among them, which needs DEBUG on (#76).
WALLED_PAGES = [path for path, _ in pages_of(VOTER)]


@pytest.fixture
def voter(db):
    return Voter.objects.create_voter("Ada")


@pytest.fixture
def client(client, voter, settings):
    settings.DEBUG = True
    client.force_login(voter)
    return client


def get_as_just_registered(client, path):
    return as_a_page(client.get(path))


def footer(page):
    return re.search(r"<footer\b.*?</footer>", page, re.S)[0]


def header(page):
    found = re.search(r"<header class=\"voter-header\".*?</header>", page, re.S)
    return found[0] if found else ""


def footer_parts(abuse_email):
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
    return [part for part, html in footer_parts(settings.ABUSE_EMAIL).items() if html not in shown]


def test_some_walled_page_is_found():
    assert "/" in WALLED_PAGES


@pytest.mark.parametrize("path", WALLED_PAGES)
def test_every_walled_voter_page_has_the_footer(client, settings, path):
    response = get_as_just_registered(client, path)

    assert response.status_code == 200
    assert missing_from_the_footer(response.text, settings) == []


@pytest.mark.parametrize("path", WALLED_PAGES)
def test_every_walled_voter_page_has_the_header_naming_the_signed_in_voter(client, path):
    shown = header(get_as_just_registered(client, path).text)

    assert '<a class="wordmark voter-header__wordmark" href="/">Test Night</a>' in shown
    assert re.search(r"<summary[^>]*>\s*Ada\s*</summary>", shown)


def test_the_header_names_whichever_voter_is_signed_in(client, db):
    client.force_login(Voter.objects.create_voter("Grete"))

    shown = header(client.get("/").text)

    assert "Grete" in shown
    assert "Ada" not in shown


def test_the_name_menu_holds_how_it_works_my_warnings_change_password_and_a_log_out_post_and_nothing_else(client):
    shown = header(client.get("/").text)
    menu = re.search(r"<details\b.*?</details>", shown, re.S)[0]

    assert re.findall(r'<a (?:class="[^"]+" )?href="([^"]+)"', menu) == ["/how-it-works/", "/warnings/", "/password/"]
    assert re.search(r'<form method="post" action="/logout/">.*?<button[^>]*>Log out</button>', menu, re.S)
    assert len(re.findall(r"<li\b", menu)) == 4


def test_the_abuse_address_comes_from_its_setting(client, settings):
    settings.ABUSE_EMAIL = "someone@example.org"

    assert 'href="mailto:someone@example.org"' in footer(client.get("/").text)


# The admin login keeps its own wordmark, which is no link home to the voter side (#76).
VOTER_FACING_PUBLIC_PAGES = [path for path in PUBLIC_PAGES if path != "/console/login/"]


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_every_public_page_has_the_footers_links_but_no_abuse_mailto_or_name_menu(client, settings, path):
    page = client.get(path).text

    assert missing_from_the_footer(page, settings) == [ABUSE_MAILTO]
    assert "mailto:" not in footer(page)
    assert "<details" not in page


@pytest.mark.parametrize("path", [*VOTER_FACING_PUBLIC_PAGES, "/join/details/"])
def test_every_voter_facing_public_page_has_the_wordmark_home_and_no_name_menu(client, path):
    page = client.get(path).text

    assert header(page).count('<a class="wordmark voter-header__wordmark" href="/">Test Night</a>') == 1
    assert "<details" not in header(page)
    assert page.count("wordmark") == 2  # the link's class and its modifier, with no second wordmark in the content


def test_the_join_details_step_has_the_wordmark_home(client, db):
    page = client.post("/join/", {"code": "local-join-code"}).text

    assert 'name="display_name"' in page
    assert '<a class="wordmark voter-header__wordmark" href="/">Test Night</a>' in header(page)


def test_the_wordmark_on_privacy_leads_a_signed_in_voter_to_the_phase_page(client):
    href = re.search(r'<a class="wordmark[^"]*" href="([^"]+)"', client.get("/privacy/").text)[1]
    response = client.get(href)

    assert href == "/"
    assert response.status_code == 200
    assert "phase/" in response.templates[0].name  # the phase page, not login
    assert re.search(r"<summary[^>]*>\s*Ada\s*</summary>", response.text)


def test_the_wordmark_on_privacy_leads_anyone_else_to_login(db):
    anonymous_client = Client()
    href = re.search(r'<a class="wordmark[^"]*" href="([^"]+)"', anonymous_client.get("/privacy/").text)[1]
    response = anonymous_client.get(href)

    assert response.status_code == 302
    assert response["Location"].startswith("/login/")
