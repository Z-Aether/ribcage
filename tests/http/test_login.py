import re
from datetime import timedelta
from urllib.parse import quote

import pytest
from django.contrib.auth import get_user
from django.contrib.auth.views import LogoutView

# Loaded before the log-out test reads Django's view, so that test holds when run alone (#70).
import ribcage.identity.views  # noqa: F401
from ribcage.identity.models import Voter
from tests.http.signing_in import PASSWORD, log_in

SIGNED_IN_AS_SAM = '<summary class="voter-menu__name">Sam</summary>'


@pytest.fixture
def sam(db):
    return Voter.objects.create_voter("Sam", PASSWORD)


def as_answered(response, typed_name):
    # The page echoes the typed name and a fresh CSRF token, twice; everything else must match (#71).
    page = re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"|"X-CSRFToken": "[^"]+"', "", response.text)
    return response.status_code, page.replace(f'value="{typed_name}"', 'value=""')


def test_a_walled_page_sends_a_signed_out_visitor_to_login(client, db):
    response = client.get("/?from=somewhere")

    assert response.status_code == 302
    assert response.headers["Location"] == f"/login/?next={quote('/?from=somewhere', safe='/')}"


def test_signing_in_goes_back_where_the_visitor_was_going(client, sam):
    login_page = client.get(client.get("/?from=somewhere").headers["Location"])
    assert 'name="next" value="/?from=somewhere"' in login_page.text

    response = log_in(client, "Sam", PASSWORD, next="/?from=somewhere")

    assert response.status_code == 302
    assert response.headers["Location"] == "/?from=somewhere"


def test_signing_in_with_no_destination_lands_on_the_phase_page(client, sam):
    response = log_in(client, "Sam", PASSWORD)

    assert response.headers["Location"] == "/"
    assert SIGNED_IN_AS_SAM in client.get("/").text


@pytest.mark.parametrize("typed", ["Sam", "sam", "SAM", " sAm "])
def test_the_right_name_and_password_sign_in_regardless_of_case(client, sam, typed):
    log_in(client, typed, PASSWORD)

    assert get_user(client) == sam


def test_a_wrong_password_and_an_unknown_name_get_the_same_response(client, sam):
    wrong_password = log_in(client, "Sam", "not-the-password")
    unknown_name = log_in(client, "Nobody", PASSWORD)

    assert as_answered(wrong_password, "Sam") == as_answered(unknown_name, "Nobody")
    assert wrong_password.status_code == 200
    assert "The display name or the password is wrong." in wrong_password.text
    assert not get_user(client).is_authenticated


def test_log_out_ends_the_session_and_lands_on_login(client, sam):
    log_in(client, "Sam", PASSWORD)

    response = client.post("/logout/")

    assert response.headers["Location"] == "/login/"
    assert not get_user(client).is_authenticated
    assert client.get("/").status_code == 302


def test_log_out_is_a_post(client, sam):
    log_in(client, "Sam", PASSWORD)

    assert client.get("/logout/").status_code == 405
    assert get_user(client) == sam


def test_a_stale_tabs_log_out_lands_on_login(client, db):
    response = client.post("/logout/")

    assert response.headers["Location"] == "/login/"


def test_a_voter_session_lasts_about_60_days(client, sam):
    log_in(client, "Sam", PASSWORD)

    lifetime = timedelta(seconds=client.cookies["sessionid"]["max-age"])

    assert timedelta(days=55) <= lifetime <= timedelta(days=65)
    assert client.session.get_expire_at_browser_close() is False


def test_the_login_page_links_the_privacy_policy(client):
    assert '<a href="/privacy/">Privacy policy</a>' in client.get("/login/").text


def test_the_login_page_wears_the_voter_skin(client):
    assert '<body data-skin="voter" ' in client.get("/login/").text


def test_making_log_out_public_leaves_djangos_logout_view_unmarked():
    # The wall's opt-out sits on our view function, never on Django's class (#70).
    assert getattr(LogoutView.as_view(), "login_required", True) is True
