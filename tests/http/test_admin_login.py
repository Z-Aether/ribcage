from datetime import timedelta
from urllib.parse import quote

import pytest
from django.conf import settings
from django.contrib.auth import get_user
from django.contrib.sessions.models import Session
from django.utils import timezone

from ribcage.identity import admin_session, backoff
from ribcage.identity.models import Voter
from tests.http.test_login import PASSWORD, log_in
from tests.http.test_login_backoff import WAIT_MESSAGE

ADMIN_LOGIN = "/console/login/"
CONSOLE = "/console/films/"
WRONG_PASSWORD = "The admin password is wrong."


def sign_in_as_the_admin(client, password=None, headers=None, **extra):
    fields = {"password": settings.ADMIN_PASSWORD if password is None else password, **extra}
    return client.post(ADMIN_LOGIN, fields, headers=headers)


def reaches_the_console(client):
    return client.get(CONSOLE).status_code == 200


@pytest.fixture(autouse=True)
def fast_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def backoff_settings(settings):
    settings.LOGIN_BACKOFF_FAILURES = 5
    settings.LOGIN_BACKOFF_WINDOW_MINUTES = 15
    settings.LOGIN_BACKOFF_WAIT_MINUTES = 1


@pytest.fixture
def sam(db):
    return Voter.objects.create_voter("Sam", PASSWORD)


def test_the_admin_login_asks_for_a_password_and_nothing_else(client, db):
    page = client.get(ADMIN_LOGIN).text

    assert 'type="password" name="password"' in page
    assert 'name="username"' not in page
    assert '<body data-skin="admin"' in page


def test_the_right_password_signs_in_and_opens_the_console(client, db):
    response = sign_in_as_the_admin(client)

    assert (response.status_code, response.headers["Location"]) == (302, "/console/")
    assert reaches_the_console(client)


def test_signing_in_makes_no_admin_row(client, db):
    sign_in_as_the_admin(client)

    assert Voter.objects.count() == 0


def test_a_wrong_password_is_refused_and_signs_nobody_in(client, db):
    response = sign_in_as_the_admin(client, "not-the-admin-password")

    assert response.status_code == 200
    assert WRONG_PASSWORD in response.text
    assert admin_session.COOKIE_NAME not in response.cookies
    assert not reaches_the_console(client)


@pytest.mark.parametrize("typed", ["", "local-admin-passwor", "local-admin-password ", "LOCAL-ADMIN-PASSWORD", "lócal-admin-password"])
def test_only_the_exact_password_signs_in(client, db, typed):
    sign_in_as_the_admin(client, typed)

    assert not reaches_the_console(client)


def test_the_admin_cookie_is_its_own_and_set_like_the_voter_session_cookie(client, db, settings):
    cookie = sign_in_as_the_admin(client).cookies[admin_session.COOKIE_NAME]

    assert admin_session.COOKIE_NAME != settings.SESSION_COOKIE_NAME
    assert (cookie["secure"], cookie["httponly"], cookie["samesite"]) == (True, True, "Lax")
    assert cookie["max-age"] == settings.SESSION_COOKIE_AGE


def test_the_admin_session_lasts_as_long_as_a_voters(client, db, settings):
    key = sign_in_as_the_admin(client).cookies[admin_session.COOKIE_NAME].value

    lasts = Session.objects.get(session_key=key).expire_date - timezone.now()

    assert abs(lasts - timedelta(seconds=settings.SESSION_COOKIE_AGE)) < timedelta(minutes=1)


def test_an_admin_page_sends_a_signed_out_visitor_to_the_admin_login_and_back(client, db):
    response = client.get("/console/roster/?from=somewhere")
    assert response.headers["Location"] == f"{ADMIN_LOGIN}?next={quote('/console/roster/?from=somewhere', safe='/')}"
    assert 'name="next" value="/console/roster/?from=somewhere"' in client.get(response.headers["Location"]).text

    signed_in = sign_in_as_the_admin(client, next="/console/roster/?from=somewhere")

    assert signed_in.headers["Location"] == "/console/roster/?from=somewhere"


def test_signing_in_never_goes_on_to_another_site(client, db):
    response = sign_in_as_the_admin(client, next="https://elsewhere.example/")

    assert response.headers["Location"] == "/console/"


def test_the_admin_session_alone_reaches_admin_pages_but_no_voter_page(client, db):
    sign_in_as_the_admin(client)

    assert reaches_the_console(client)
    assert client.get("/").headers["Location"].startswith("/login/")
    assert not get_user(client).is_authenticated


def test_the_voter_session_alone_reaches_voter_pages_but_no_admin_page(client, sam):
    log_in(client, "Sam", PASSWORD)

    assert client.get("/").status_code == 200
    assert client.get(CONSOLE).headers["Location"].startswith(ADMIN_LOGIN)


@pytest.mark.parametrize("admin_first", [True, False], ids=["admin-first", "voter-first"])
def test_both_sessions_are_held_at_once_in_either_order(client, sam, admin_first):
    signings = [lambda: sign_in_as_the_admin(client), lambda: log_in(client, "Sam", PASSWORD)]
    for sign in signings if admin_first else reversed(signings):
        sign()

    assert reaches_the_console(client)
    assert get_user(client) == sam
    assert client.get("/").status_code == 200


def test_admin_log_out_leaves_the_voter_signed_in(client, sam):
    log_in(client, "Sam", PASSWORD)
    sign_in_as_the_admin(client)

    response = client.post("/console/logout/")

    assert (response.status_code, response.headers["Location"]) == (302, ADMIN_LOGIN)
    assert not reaches_the_console(client)
    assert get_user(client) == sam


def test_voter_log_out_leaves_the_admin_signed_in(client, sam):
    sign_in_as_the_admin(client)
    log_in(client, "Sam", PASSWORD)

    client.post("/logout/")

    assert not get_user(client).is_authenticated
    assert reaches_the_console(client)


def test_admin_log_out_ends_the_session_on_the_server_not_just_the_cookie(client, db):
    key = sign_in_as_the_admin(client).cookies[admin_session.COOKIE_NAME].value

    client.post("/console/logout/")
    client.cookies[admin_session.COOKIE_NAME] = key

    assert not reaches_the_console(client)


def test_admin_log_out_from_a_tab_already_signed_out_lands_on_the_admin_login(client, db):
    response = client.post("/console/logout/")

    assert (response.status_code, response.headers["Location"]) == (302, ADMIN_LOGIN)


def test_signing_in_again_replaces_the_admin_session(client, db):
    first = sign_in_as_the_admin(client).cookies[admin_session.COOKIE_NAME].value
    second = sign_in_as_the_admin(client).cookies[admin_session.COOKIE_NAME].value

    client.cookies[admin_session.COOKIE_NAME] = first

    assert first != second
    assert not reaches_the_console(client)


def test_a_planted_admin_cookie_reaches_nothing(client, db):
    client.cookies[admin_session.COOKIE_NAME] = "a-session-the-database-never-held"

    assert not reaches_the_console(client)


def test_a_voter_session_key_in_the_admin_cookie_reaches_nothing(client, sam):
    log_in(client, "Sam", PASSWORD)
    client.cookies[admin_session.COOKIE_NAME] = client.cookies["sessionid"].value

    assert not reaches_the_console(client)


def test_a_new_admin_password_ends_every_admin_session(client, db, settings):
    sign_in_as_the_admin(client)

    settings.ADMIN_PASSWORD = "a-new-admin-password"

    assert not reaches_the_console(client)


def fail(client, times):
    return [sign_in_as_the_admin(client, "not-the-admin-password") for _ in range(times)]


def test_the_admin_login_backs_off_like_the_voter_login(client, db, clock):
    short_of_the_limit = fail(client, 4)
    assert not any(WAIT_MESSAGE in response.text for response in short_of_the_limit)

    fifth = sign_in_as_the_admin(client, "not-the-admin-password")
    assert WAIT_MESSAGE in fifth.text
    assert WRONG_PASSWORD not in fifth.text


def test_during_the_wait_even_the_right_admin_password_is_refused(client, db, clock):
    fail(client, 5)
    clock.advance(seconds=59)

    assert WAIT_MESSAGE in sign_in_as_the_admin(client).text
    assert not reaches_the_console(client)


def test_after_the_wait_the_right_admin_password_works_and_clears_the_count(client, db, clock):
    fail(client, 5)
    clock.advance(minutes=1)

    sign_in_as_the_admin(client)

    assert reaches_the_console(client)
    assert not backoff.LoginFailure.objects.filter(key=backoff.ADMIN_KEY).exists()


def test_the_admins_wait_leaves_voters_alone(client, sam, clock):
    fail(client, 5)

    log_in(client, "Sam", PASSWORD)

    assert get_user(client) == sam


def test_a_voter_name_of_admin_has_a_count_apart_from_the_admin_logins(client, db, clock):
    for _ in range(5):
        log_in(client, "admin", "not-the-password")

    sign_in_as_the_admin(client)

    assert reaches_the_console(client)
