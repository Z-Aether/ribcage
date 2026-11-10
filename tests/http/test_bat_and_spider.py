"""Every page loads the bat's flight but the admin's (#99)."""

import pytest
from django.templatetags.static import static

from ribcage.identity.models import Voter
from tests.http.routes import ADMIN, VOTER, as_a_page, pages_of, public_pages, routes_of
from tests.http.signing_in import ADMIN_LOGIN, sign_in_as_the_admin

VOTER_PAGES = [path for path, _ in pages_of(VOTER)]
VOTER_FACING_PUBLIC_PAGES = [path for path, _ in public_pages() if path != ADMIN_LOGIN]
ADMIN_ROUTES = [path for path, _ in routes_of(ADMIN)]


def bat_script():
    # Read at test time: with DEBUG off the collected static files' names carry their hashes (#46).
    return f'<script src="{static("components/bat.js")}" defer></script>'


@pytest.fixture
def voter(client, db, settings):
    # The gallery is a voter page only with DEBUG on (#58).
    settings.DEBUG = True
    client.force_login(Voter.objects.create_voter("Ada"))
    return client


@pytest.fixture
def admin(client, db):
    sign_in_as_the_admin(client)
    return client


@pytest.mark.parametrize("path", VOTER_PAGES)
def test_every_voter_page_loads_the_bats_flight(voter, path):
    response = as_a_page(voter.get(path))

    assert response.status_code == 200
    assert bat_script() in response.text


@pytest.mark.parametrize("path", VOTER_FACING_PUBLIC_PAGES)
def test_every_voter_facing_public_page_loads_the_bats_flight(client, db, path):
    assert bat_script() in client.get(path).text


@pytest.mark.parametrize("path", [*ADMIN_ROUTES, ADMIN_LOGIN])
def test_no_admin_page_loads_the_bats_flight(admin, path):
    response = as_a_page(admin.get(path, follow=True))

    assert response.status_code == 200
    assert bat_script() not in response.text


def test_the_app_serves_the_bats_flight_with_debug_off(client, settings):
    assert not settings.DEBUG

    assert client.get(static("components/bat.js")).status_code == 200
