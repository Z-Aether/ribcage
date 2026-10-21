import pytest
from django.contrib.auth import get_user
from django.http import HttpResponse
from django.test import Client
from django.urls import path

import ribcage.urls
from ribcage.identity.models import Voter
from ribcage.identity.views import change_password
from ribcage.phase.check import phase_window
from ribcage.phase.order import PHASES
from tests.http.routes import VOTER, routes_of
from tests.http.test_password_reset import NEW_PASSWORD, reset, shown_password
from tests.http.test_phase import walk_to
from tests.http.test_registration import PASSWORD

CHANGE = "/password/"
WRITE = "/test-only/write/"
HTMX = {"HX-Request": "true"}
OTHER_VOTER_ROUTES = [path for path, entry in routes_of(VOTER) if entry.name != "change_password"]


@phase_window(*PHASES)
def a_voter_write(request):
    request.user.display_name = "Written"
    request.user.save()
    return HttpResponse("written")


# A test-only voter write, open in every phase, so only the forced change can refuse it (#78, #80).
urlpatterns = [*ribcage.urls.urlpatterns, path("test-only/write/", a_voter_write)]


@pytest.fixture(autouse=True)
def fast_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def dani(db):
    return Voter.objects.create_voter("Dani", PASSWORD)


@pytest.fixture
def shown(admin, dani):
    """The password the admin was shown on resetting Dani's."""
    return shown_password(reset(admin, dani).text)


@pytest.fixture
def browser(shown):
    """Dani's browser, signed in with the password the admin sent."""
    browser = Client()
    assert browser.post("/login/", {"username": "Dani", "password": shown}).status_code == 302
    return browser


def change(browser, current, new=NEW_PASSWORD, again=None):
    return browser.post(CHANGE, {"old_password": current, "new_password1": new, "new_password2": new if again is None else again})


def must_change(voter):
    voter.refresh_from_db()
    return voter.must_change_password


@pytest.mark.parametrize("next_page", ["", "?next=/", "?next=/welcome/", "?next=/password/changed/"])
def test_signing_in_with_the_shown_password_lands_on_the_change_form(shown, next_page):
    browser = Client()

    response = browser.post(f"/login/{next_page}", {"username": "Dani", "password": shown}, follow=True)

    assert response.redirect_chain[-1] == (CHANGE, 302)
    assert "<h1>Choose your own password</h1>" in response.text
    assert "Type the one they sent you as your current password" in response.text


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("path", OTHER_VOTER_ROUTES)
def test_every_other_voter_route_sends_a_forced_voter_to_the_change_form(browser, path, method):
    response = getattr(browser, method)(path)

    assert (response.status_code, response.headers["Location"]) == (302, CHANGE)


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("path", OTHER_VOTER_ROUTES)
def test_an_htmx_request_has_htmx_load_the_change_form(browser, path, method):
    response = getattr(browser, method)(path, headers=HTMX)

    assert (response.status_code, response.headers["HX-Redirect"], response.text) == (200, CHANGE, "")


@pytest.mark.urls(__name__)
@pytest.mark.parametrize("headers", [None, HTMX])
def test_a_forced_voters_post_writes_nothing(browser, dani, headers):
    browser.post(WRITE, headers=headers)

    dani.refresh_from_db()
    assert dani.display_name == "Dani"


def test_the_change_form_opens(browser):
    assert browser.get(CHANGE).status_code == 200


def test_log_out_works(browser):
    response = browser.post("/logout/")

    assert response.headers["Location"] == "/login/"
    assert not get_user(browser).is_authenticated


@pytest.mark.parametrize("path", ["/privacy/", "/login/", "/join/"])
def test_public_pages_stay_open(browser, path):
    assert browser.get(path).status_code == 200


def test_the_admin_console_stays_open_to_a_browser_also_holding_a_forced_voter(admin, dani):
    assert admin.post("/login/", {"username": "Dani", "password": shown_password(reset(admin, dani).text)}).status_code == 302

    assert admin.get("/console/roster/").status_code == 200


def test_a_weak_new_password_is_refused_and_the_change_still_forced(browser, dani, shown):
    response = change(browser, shown, new="password123")

    assert "too common" in response.text
    assert must_change(dani)
    assert browser.get("/").headers["Location"] == CHANGE


def test_a_wrong_current_password_is_refused(browser, dani):
    response = change(browser, PASSWORD)

    assert "Your current password is wrong." in response.text
    assert must_change(dani)


def test_after_the_change_every_page_works_and_the_flag_is_cleared(browser, dani, shown):
    response = change(browser, shown)

    assert response.headers["Location"] == "/password/changed/"
    assert not must_change(dani)
    assert dani.check_password(NEW_PASSWORD)
    for path in ["/", "/password/changed/", CHANGE]:
        assert browser.get(path).status_code == 200
    assert "<h1>Change password</h1>" in browser.get(CHANGE).text


def test_after_the_change_the_new_password_signs_in_anywhere_straight_to_the_phase_page(browser, shown):
    change(browser, shown)

    response = Client().post("/login/", {"username": "Dani", "password": NEW_PASSWORD})

    assert response.headers["Location"] == "/"


def test_the_forced_change_is_the_change_form_an_account_action(browser):
    assert browser.get(CHANGE).resolver_match.func is change_password
    assert change_password.account_action


@pytest.mark.parametrize("phase", PHASES)
def test_the_forced_change_works_in_every_phase(browser, dani, shown, phase):
    walk_to(phase)

    response = change(browser, shown)

    assert response.headers["Location"] == "/password/changed/"
    assert not must_change(dani)


def test_a_voter_never_reset_is_never_forced(db):
    voter = Voter.objects.create_voter("Ada", PASSWORD)
    browser = Client()
    browser.force_login(voter)

    assert not voter.must_change_password
    assert browser.get("/").status_code == 200
