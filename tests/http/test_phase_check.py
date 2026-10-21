import pytest
from django.contrib.auth import get_user
from django.http import HttpResponse
from django.test import Client
from django.urls import path

import ribcage.urls
from ribcage.identity.models import Voter
from ribcage.phase.check import phase_window
from ribcage.phase.order import PHASES, Phase
from tests.http.routes import ADMIN, PUBLIC, VOTER, routes_of
from tests.http.test_phase import PAGE_HEADINGS, walk_to

SUGGEST, APPROVE, VOTE, PICK, RUN = Phase
WINDOW = {SUGGEST, APPROVE}
OUTSIDE_THE_WINDOW = [phase for phase in PHASES if phase not in WINDOW]
ACTION = "/test-only/rename/"
HTMX = {"HX-Request": "true"}


@phase_window(SUGGEST, APPROVE)
def a_windowed_rename(request):
    if request.method == "GET":
        return HttpResponse("the form")
    request.user.display_name = request.POST["display_name"]
    request.user.save()
    return HttpResponse("renamed")


# A test-only voter write, so no production route exists for the test's sake (#76, #78).
urlpatterns = [*ribcage.urls.urlpatterns, path("test-only/rename/", a_windowed_rename)]
with_the_test_action = pytest.mark.urls(__name__)


@pytest.fixture
def ada(db):
    return Voter.objects.create_voter("Ada")


@pytest.fixture
def client(client, ada):
    client.force_login(ada)
    return client


def rename(client, headers=None):
    return client.post(ACTION, {"display_name": "Grete"}, headers=headers)


def display_name(voter):
    voter.refresh_from_db()
    return voter.display_name


@with_the_test_action
@pytest.mark.parametrize("phase", sorted(WINDOW, key=PHASES.index))
def test_a_post_inside_its_window_writes(client, ada, phase):
    walk_to(phase)

    response = rename(client)

    assert (response.status_code, response.text) == (200, "renamed")
    assert display_name(ada) == "Grete"


@with_the_test_action
@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
def test_a_plain_post_outside_its_window_writes_nothing_and_is_sent_to_the_phase_page(client, ada, phase):
    walk_to(phase)

    response = rename(client)

    assert (response.status_code, response.headers["Location"]) == (302, "/")
    assert display_name(ada) == "Ada"


@with_the_test_action
@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
def test_an_htmx_post_outside_its_window_writes_nothing_and_has_htmx_load_the_phase_page(client, ada, phase):
    walk_to(phase)

    response = rename(client, headers=HTMX)

    # HX-Redirect sends the whole tab to the address, whatever the status, before any swap (#78).
    assert (response.status_code, response.headers["HX-Redirect"], response.text) == (200, "/", "")
    assert display_name(ada) == "Ada"


@with_the_test_action
def test_a_refused_post_lands_on_the_current_phase_page(client):
    walk_to(VOTE)

    response = client.post(ACTION, {"display_name": "Grete"}, follow=True)

    assert f"<h1>{PAGE_HEADINGS[VOTE]}</h1>" in response.text


@with_the_test_action
def test_reading_a_windowed_view_outside_its_window_is_not_refused(client):
    walk_to(VOTE)

    response = client.get(ACTION)

    assert (response.status_code, response.text) == (200, "the form")


def test_the_window_is_declared_on_the_view_itself():
    assert a_windowed_rename.phase_window == WINDOW


def marks(entry):
    return {mark for mark in ["phase_window", "account_action"] if getattr(entry.callback, mark, None)}


def accepts_a_write(path, voter):
    # A client of its own per route, so a probe that ends its session can't skew the next (#78).
    probe = Client()
    probe.force_login(voter)
    return any(getattr(probe, method)(path).status_code != 405 for method in ["post", "put", "patch", "delete"])


def voter_posts():
    """Voter routes, by name, that accept a POST, PUT, PATCH or DELETE from a signed-in voter, each with its phase-check marks."""
    voter = Voter.objects.create_voter("Probe")
    return {entry.name or path: marks(entry) for path, entry in routes_of(VOTER) if accepts_a_write(path, voter)}


def test_every_voter_post_either_declares_a_window_or_is_an_account_action(db):
    # A later milestone's voter write can't forget its window, and none is both (#34, #78).
    assert {name: found for name, found in voter_posts().items() if len(found) != 1} == {}


def test_the_probe_finds_a_voter_post(db):
    assert voter_posts()["change_password"] == {"account_action"}


def test_no_admin_route_declares_a_window():
    # Admin surfaces are never gated by the phase (#15).
    assert [entry.name for _, entry in routes_of(ADMIN) if hasattr(entry.callback, "phase_window")] == []


def test_log_out_is_an_account_action_though_outside_the_wall():
    # Public, so the voter-route invariant never reads its mark; held here instead (#70, #78).
    assert [marks(entry) for _, entry in routes_of(PUBLIC) if entry.name == "logout"] == [{"account_action"}]


@pytest.mark.parametrize("phase", PHASES)
def test_log_out_works_in_every_phase(client, phase):
    walk_to(phase)

    response = client.post("/logout/")

    assert response.headers["Location"] == "/login/"
    assert not get_user(client).is_authenticated


@pytest.mark.parametrize("phase", PHASES)
def test_change_password_works_in_every_phase(client, ada, settings, phase):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    ada.set_password("first-password-of-ours")
    ada.save()
    client.force_login(ada)
    walk_to(phase)
    new_password = "a-second-one-entirely"

    response = client.post(
        "/password/",
        {"old_password": "first-password-of-ours", "new_password1": new_password, "new_password2": new_password},
    )

    assert response.headers["Location"] == "/password/changed/"
    ada.refresh_from_db()
    assert ada.check_password(new_password)
