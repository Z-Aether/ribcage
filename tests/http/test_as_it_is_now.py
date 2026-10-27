"""Back and Forward show a voter or admin page as the server has it now: what the server sends for it, and nothing of it on public pages (#84)."""

import pytest
from django.templatetags.static import static

from ribcage.identity.models import Voter
from tests.http.routes import ADMIN, VOTER, as_a_page, public_pages, routes_of
from tests.http.signing_in import sign_in_as_the_admin


def reload_on_restore():
    # Read at test time: with DEBUG off the collected static files' names carry their hashes (#46).
    return f'<script src="{static("shell/as-it-is-now.js")}" defer></script>'


VOTER_ROUTES = [path for path, _ in routes_of(VOTER)]
ADMIN_ROUTES = [path for path, _ in routes_of(ADMIN)]
PUBLIC_PAGES = [path for path, _ in public_pages()]
# Django's own login view is never cached, from before #84; the shell adds nothing to it.
SETS_ITS_OWN_CACHE_HEADERS = {"/login/"}


@pytest.fixture
def voter(client, db, settings):
    # The gallery is a voter page only with DEBUG on (#58).
    settings.DEBUG = True
    client.force_login(Voter.objects.create_voter("Ada"))
    return client


def anonymous(client):
    return client


def signed_in_as_a_voter(client):
    client.force_login(Voter.objects.create_voter("Ada"))
    return client


def signed_in_as_the_admin(client):
    sign_in_as_the_admin(client)
    return client


@pytest.mark.parametrize("path", VOTER_ROUTES)
def test_every_voter_route_is_never_stored_by_the_browser(voter, path):
    response = voter.get(path)

    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_every_admin_route_is_never_stored_by_the_browser(admin, path):
    response = admin.get(path)

    assert "no-store" in response.headers["Cache-Control"]


def test_the_walls_redirect_to_login_is_never_stored_either(client, db):
    # A page cached from before log out would otherwise come back on Back (#84).
    response = client.get("/")

    assert response.status_code == 302
    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.parametrize("path", VOTER_ROUTES)
def test_every_voter_page_reloads_when_back_or_forward_restores_it(voter, path):
    response = as_a_page(voter.get(path, follow=True))

    assert response.status_code == 200
    assert reload_on_restore() in response.text


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_every_admin_page_reloads_when_back_or_forward_restores_it(admin, path):
    response = as_a_page(admin.get(path, follow=True))

    assert response.status_code == 200
    assert reload_on_restore() in response.text


@pytest.mark.parametrize("visitor", [anonymous, signed_in_as_a_voter, signed_in_as_the_admin])
@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_no_public_page_carries_the_header_or_the_reload(client, db, visitor, path):
    response = visitor(client).get(path)

    assert response.status_code == 200
    assert path in SETS_ITS_OWN_CACHE_HEADERS or "Cache-Control" not in response.headers
    assert reload_on_restore() not in response.text
