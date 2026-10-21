from datetime import timedelta

import pytest
from django.contrib.auth import get_user

from ribcage.identity import backoff
from ribcage.identity.models import Voter
from tests.http.test_login import PASSWORD, as_answered, log_in

WAIT_MESSAGE = "Too many attempts. Try again in a minute."
WRONG = "not-the-password"


@pytest.fixture(autouse=True)
def fast_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def sam(db):
    return Voter.objects.create_voter("Sam", PASSWORD)


@pytest.fixture(autouse=True)
def backoff_settings(settings):
    settings.LOGIN_BACKOFF_FAILURES = 5
    settings.LOGIN_BACKOFF_WINDOW_MINUTES = 15
    settings.LOGIN_BACKOFF_WAIT_MINUTES = 1


def fail(client, display_name, times):
    return [log_in(client, display_name, WRONG) for _ in range(times)]


def test_failures_short_of_the_limit_bring_no_wait(client, sam, clock):
    responses = fail(client, "Sam", 4)

    assert not any(WAIT_MESSAGE in response.text for response in responses)
    log_in(client, "Sam", PASSWORD)
    assert get_user(client) == sam


def test_the_nth_failure_inside_the_window_brings_the_wait(client, sam, clock):
    fail(client, "Sam", 4)
    clock.advance(minutes=14)

    response = log_in(client, "Sam", WRONG)

    assert response.status_code == 200
    assert WAIT_MESSAGE in response.text
    assert "The display name or the password is wrong." not in response.text


def test_during_the_wait_even_the_right_password_is_refused(client, sam, clock):
    fail(client, "Sam", 5)
    clock.advance(seconds=59)

    response = log_in(client, "Sam", PASSWORD)

    assert WAIT_MESSAGE in response.text
    assert not get_user(client).is_authenticated


def test_after_the_wait_the_right_password_works(client, sam, clock):
    fail(client, "Sam", 5)
    clock.advance(minutes=1)

    log_in(client, "Sam", PASSWORD)

    assert get_user(client) == sam


def test_attempts_during_the_wait_do_not_lengthen_it(client, sam, clock):
    fail(client, "Sam", 5)
    for _ in range(10):
        clock.advance(seconds=5)
        log_in(client, "Sam", WRONG)
    clock.advance(seconds=10)

    log_in(client, "Sam", PASSWORD)

    assert get_user(client) == sam


def test_a_failure_after_the_wait_brings_another_wait(client, sam, clock):
    fail(client, "Sam", 5)
    clock.advance(minutes=1)

    assert WAIT_MESSAGE in log_in(client, "Sam", WRONG).text
    assert WAIT_MESSAGE in log_in(client, "Sam", PASSWORD).text


def test_a_success_clears_the_count(client, sam, clock):
    fail(client, "Sam", 4)
    log_in(client, "Sam", PASSWORD)
    client.post("/logout/")

    responses = fail(client, "Sam", 4)

    assert not any(WAIT_MESSAGE in response.text for response in responses)
    log_in(client, "Sam", PASSWORD)
    assert get_user(client) == sam


def test_failures_outside_the_window_do_not_count(client, sam, clock):
    fail(client, "Sam", 4)
    clock.advance(minutes=15, seconds=1)

    response = log_in(client, "Sam", WRONG)

    assert WAIT_MESSAGE not in response.text
    log_in(client, "Sam", PASSWORD)
    assert get_user(client) == sam


def test_old_failures_are_pruned_as_the_count_is_read(client, sam, clock):
    fail(client, "Sam", 4)
    clock.advance(minutes=30)

    log_in(client, "Nobody", WRONG)

    assert list(backoff.LoginFailure.objects.values_list("key", flat=True)) == [backoff.voter_key("Nobody")]


def test_an_unknown_name_backs_off_exactly_like_a_known_one(client, sam, clock):
    known = fail(client, "Sam", 6)
    unknown = fail(client, "Nobody", 6)

    assert [as_answered(response, "Sam") for response in known] == [as_answered(response, "Nobody") for response in unknown]
    assert WAIT_MESSAGE in unknown[-1].text


def test_spellings_of_one_name_share_one_count(client, sam, clock):
    for typed in ["Sam", " sam ", "SAM", "sAm", " Sam"]:
        log_in(client, typed, WRONG)

    assert WAIT_MESSAGE in log_in(client, "sam", PASSWORD).text


def test_one_names_wait_leaves_another_name_alone(client, sam, clock):
    fail(client, "Nobody", 5)

    log_in(client, "Sam", PASSWORD)

    assert get_user(client) == sam


def test_a_longer_wait_names_its_minutes(client, sam, clock, settings):
    settings.LOGIN_BACKOFF_WAIT_MINUTES = 3
    fail(client, "Sam", 5)
    clock.advance(seconds=30)

    assert "Too many attempts. Try again in 3 minutes." in log_in(client, "Sam", PASSWORD).text


def test_any_key_backs_off_through_the_same_calls(db, clock):
    # The admin login reuses this under a key of its own (#60, #76).
    for _ in range(5):
        assert backoff.wait("some-other-login") is None
        backoff.record_failure("some-other-login")

    assert backoff.wait("some-other-login") == timedelta(minutes=1)
    assert backoff.wait(backoff.voter_key("some-other-login")) is None
    backoff.clear("some-other-login")
    assert backoff.wait("some-other-login") is None
