import pytest
from django.test import Client

from ribcage.identity.models import Voter

PASSWORD_CHANGE = "/password/"
PASSWORD = "lantern-in-the-kitchen"
NEW_PASSWORD = "carved-pumpkin-grin"


@pytest.fixture(autouse=True)
def fast_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def voter(db):
    return Voter.objects.create_voter("Ada", PASSWORD)


@pytest.fixture
def client(client, voter):
    client.force_login(voter)
    return client


def change(client, current=PASSWORD, new=NEW_PASSWORD, again=None):
    return client.post(
        PASSWORD_CHANGE,
        {"old_password": current, "new_password1": new, "new_password2": new if again is None else again},
    )


def password_still_works(voter, password):
    voter.refresh_from_db()
    return voter.check_password(password)


def test_the_form_asks_for_the_current_password_then_the_new_one_twice(client):
    page = client.get(PASSWORD_CHANGE).text

    assert page.index('name="old_password"') < page.index('name="new_password1"') < page.index('name="new_password2"')


def test_a_wrong_current_password_is_refused(client, voter):
    response = change(client, current="not-my-password")

    assert response.status_code == 200
    assert "Your current password is wrong." in response.text
    assert password_still_works(voter, PASSWORD)


def test_new_passwords_that_differ_are_refused(client, voter):
    response = change(client, again="carved-pumpkin-frown")

    assert response.status_code == 200
    assert "The two passwords differ." in response.text
    assert password_still_works(voter, PASSWORD)


@pytest.mark.parametrize(
    "weak, why",
    [
        pytest.param("Ada1!", "similar", id="like the display name"),
        pytest.param("k9-bat", "too short", id="too short"),
        pytest.param("password123", "too common", id="too common"),
        pytest.param("8675309142", "entirely numeric", id="all digits"),
    ],
)
def test_a_weak_new_password_is_refused_by_djangos_four_checks(client, voter, weak, why):
    response = change(client, new=weak)

    assert response.status_code == 200
    assert why in response.text
    assert password_still_works(voter, PASSWORD)


def test_a_successful_change_sets_the_new_password(client, voter):
    response = change(client)

    assert response.status_code == 302
    assert password_still_works(voter, NEW_PASSWORD)


def test_a_successful_change_keeps_the_current_session(client):
    change(client)

    assert client.get("/").status_code == 200


def test_a_successful_change_ends_another_session_of_the_same_voter(client, voter):
    other_device = Client()
    other_device.post("/login/", {"username": "Ada", "password": PASSWORD})
    assert other_device.get("/").status_code == 200

    change(client)

    assert other_device.get("/").headers["Location"] == "/login/?next=/"


def test_a_successful_change_leaves_another_voters_session_alone(client, db):
    Voter.objects.create_voter("Grete", PASSWORD)
    someone_else = Client()
    someone_else.post("/login/", {"username": "Grete", "password": PASSWORD})

    change(client)

    assert someone_else.get("/").status_code == 200


def test_a_successful_change_says_so(client):
    page = client.get(change(client).headers["Location"]).text

    assert "Your password is changed." in page


def test_password_change_is_behind_the_login_wall(db):
    assert Client().get(PASSWORD_CHANGE).headers["Location"] == f"/login/?next={PASSWORD_CHANGE}"
