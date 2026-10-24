"""The bat flies in every skin but admin, and the theme stills it and the spider under reduced motion (#99)."""

import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static

from ribcage.identity.models import Voter
from ribcage.identity.views import WELCOME_PENDING
from tests.http.routes import ADMIN, VOTER, as_a_page, pages_of, public_pages, routes_of
from tests.http.signing_in import ADMIN_LOGIN, sign_in_as_the_admin

VOTER_PAGES = [path for path, _ in pages_of(VOTER)]
VOTER_FACING_PUBLIC_PAGES = [path for path, _ in public_pages() if path != ADMIN_LOGIN]
ADMIN_ROUTES = [path for path, _ in routes_of(ADMIN)]

SPIDER = '[data-skin="voter"] .film-card.is-open .film-card__poster::after'
FLYING_BAT = '[data-skin]:not([data-skin="admin"]) .wordmark.is-flying::after'


def bat_script():
    # Read at test time: with DEBUG off the collected static files' names carry their hashes (#46).
    return f'<script src="{static("components/bat.js")}" defer></script>'


def theme():
    return Path(finders.find("theme/theme.css")).read_text(encoding="utf-8")


def rule_for(selector, css):
    """The declarations of the first rule whose selector list holds `selector`."""
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if selector in [part.strip() for part in selectors.split(",")]:
            return body
    return None


def reduced_motion(css):
    return re.search(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", css, re.S)[1]


@pytest.fixture
def voter(client, db, settings):
    # The gallery is a voter page only with DEBUG on (#58).
    settings.DEBUG = True
    client.force_login(Voter.objects.create_voter("Ada"))
    session = client.session
    session[WELCOME_PENDING] = True
    session.save()
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


def test_the_bat_flies_and_flaps_in_every_skin_but_admin():
    animation = rule_for(FLYING_BAT, theme())

    assert animation is not None
    assert "bat-flight" in animation and "bat-flap" in animation


def test_the_bat_script_skips_only_the_admin_skin():
    script = Path(finders.find("components/bat.js")).read_text(encoding="utf-8")

    assert 'dataset.skin !== "admin"' in script


def test_the_spider_bounces_on_silk_that_hangs_from_the_posters_bottom_edge():
    spider = rule_for(SPIDER, theme())

    assert "spider-bounce" in spider
    assert "transform" not in spider  # moving the whole thread would lift its top off the poster


def test_reduced_motion_stills_the_flying_bat_and_the_spider():
    stilled = reduced_motion(theme())

    assert "animation: none" in rule_for(FLYING_BAT, stilled)
    assert "animation: none" in rule_for(SPIDER, stilled)


def test_the_admin_skin_keeps_the_spider_off_its_cards():
    assert "content: none" in rule_for('[data-skin="admin"] .film-card.is-open .film-card__poster::after', theme())


def test_the_app_serves_the_bats_flight_with_debug_off(client, settings):
    assert not settings.DEBUG

    assert client.get(static("components/bat.js")).status_code == 200
