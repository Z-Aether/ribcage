"""Every page shows the marathon's name from the environment and never the codename (#129)."""

import re

import pytest
from django.db import transaction
from django.test import Client

from ribcage.phase.order import Phase
from tests.http.routes import ADMIN, public_pages
from tests.http.sweeping import sweep
from tests.http.test_phase import walk_to
from tests.http.test_watched_privacy import cast  # noqa: F401

NAME = "NAMESENTINEL Maraton á"
TITLE = re.compile(r"<title>(.*?)</title>", re.DOTALL)


def titled(answer):
    found = TITLE.search(answer.text)
    return found.group(1) if found else None


@pytest.fixture(autouse=True)
def named(settings):
    settings.MARATHON_NAME = NAME


@pytest.mark.parametrize("phase", list(Phase))
def test_every_voter_and_admin_page_and_fragment_shows_the_name_and_never_the_codename(cast, phase):  # noqa: F811
    viewers = {"voter": cast["clients"]["observer"], ADMIN: cast["clients"][ADMIN]}
    with transaction.atomic():
        walk_to(phase)
        answers = list(sweep(viewers, cast["films"]))
        transaction.set_rollback(True)

    pages = [answer for answer in answers if answer.status == 200 and titled(answer) is not None]
    assert len(pages) > 5
    for answer in answers:
        assert "Ribcage" not in answer.text, answer.where
    for page in pages:
        assert titled(page).strip() in (NAME, f"{NAME}") or titled(page).endswith(f" · {NAME}"), page.where
        assert f">{NAME}</a>" in page.text or f'>{NAME}</p>' in page.text, page.where


@pytest.mark.parametrize("path", [path for path, _ in public_pages()])
def test_every_public_page_shows_the_name_and_never_the_codename(client, db, path):
    response = client.get(path)
    if response.status_code == 405:
        pytest.skip("answers POST alone")

    assert "Ribcage" not in response.text
    assert f"· {NAME}</title>" in response.text
    assert f">{NAME}</a>" in response.text or f">{NAME}</p>" in response.text


def test_the_privacy_policy_names_the_marathon_in_its_opening_sentence(client, db):
    page = client.get("/privacy/").text

    assert f"<p>{NAME} is a web app" in page
    assert "[Marathon name]" not in page


def test_the_privacy_policy_escapes_the_name(client, db, settings):
    settings.MARATHON_NAME = "<b>Night</b>"

    assert "<p>&lt;b&gt;Night&lt;/b&gt; is a web app" in client.get("/privacy/").text


def test_how_it_works_names_the_marathon(client, voters):
    client.force_login(voters["ada"])

    page = client.get("/how-it-works/").text

    assert f"<h1>Welcome to {NAME}</h1>" in page
    assert f"<p>{NAME} is where" in page
    assert "Ribcage" not in page


def test_the_admin_login_names_the_marathon(client, db):
    page = client.get("/console/login/").text

    assert f'<p class="wordmark">{NAME}</p>' in page
    assert "Ribcage" not in page


def test_the_gallery_names_the_marathon(client, voters, settings):
    settings.DEBUG = True
    client.force_login(voters["ada"])

    page = client.get("/gallery/").text

    assert f'<p class="wordmark">{NAME}</p>' in page
    assert "Ribcage" not in page


def test_the_join_details_page_names_the_marathon_in_its_title_and_never_the_codename(client, db):
    page = client.post("/join/", {"code": "local-join-code"}).text

    assert f"· {NAME}</title>" in page
    assert "Ribcage" not in page
