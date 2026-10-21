import pytest

from ribcage.identity import admin_session
from ribcage.identity.models import Voter
from tests.http.routes import (
    ADMIN,
    PUBLIC,
    PUBLIC_POSTS,
    VOTER,
    address,
    as_a_page,
    kind,
    pages_of,
    public_pages,
    route_templates,
    routes,
    routes_of,
)
from tests.http.test_admin_login import sign_in_as_the_admin

# Public pages allowed to query, by URL name: the one place an exception goes, with its ticket.
QUERYING_PUBLIC_PAGES = set()

PUBLIC_PAGES_THAT_MUST_NOT_QUERY = [path for path, entry in public_pages() if entry.name not in QUERYING_PUBLIC_PAGES]


def anonymous(client):
    return client


def with_stale_sessions(client):
    client.cookies["sessionid"] = "a-session-the-database-never-held"
    client.cookies[admin_session.COOKIE_NAME] = "an-admin-session-the-database-never-held"
    client.cookies["csrftoken"] = "a" * 32
    return client


def signed_in_as_a_voter(client):
    client.force_login(Voter.objects.create_voter("Ada"))
    client.cookies["csrftoken"] = "a" * 32
    return client


def signed_in_as_a_voter_who_must_change_their_password(client):
    voter = Voter.objects.create_voter("Ada")
    voter.must_change_password = True
    voter.save()
    client.force_login(voter)
    client.cookies["csrftoken"] = "a" * 32
    return client


def signed_in_as_the_admin(client):
    sign_in_as_the_admin(client)
    return client


def signed_in_as_both(client):
    return signed_in_as_the_admin(signed_in_as_a_voter(client))


def test_every_route_is_exactly_one_of_public_voter_or_admin():
    """Guards hand-set marks only: admin_required always sets login_not_required too."""
    assert [path for path, entry in routes() if kind(entry) not in {PUBLIC, VOTER, ADMIN}] == []


def test_every_public_page_has_a_fixed_address_that_renders():
    # The zero-query check needs the page itself, which a sample id might not find (#76).
    public_page_names = {entry.name for _, entry in public_pages()}
    assert [template for template, entry in route_templates() if entry.name in public_page_names and "<" in template] == []


def test_a_route_with_a_converter_is_requested_at_a_sample_address():
    assert address("/console/roster/<int:pk>/<slug:name>/<film>/") == "/console/roster/1/x/x/"


@pytest.mark.parametrize(
    ("name", "route_kind"),
    [
        *[(name, PUBLIC) for name in ["privacy", "login", "join", "join_details", "logout", "admin_login", "admin_logout"]],
        *[(name, VOTER) for name in ["phase_page", "welcome", "change_password", "password_changed", "gallery"]],
        *[(name, ADMIN) for name in ["console", "console_phase", "console_phase_move", "console_films", "console_pick", "console_roster", "console_roster_remove", "console_roster_reset"]],
    ],
)
def test_each_known_route_is_found_as_its_kind(name, route_kind):
    assert name in [entry.name for _, entry in routes_of(route_kind)]


def test_the_public_routes_that_answer_post_alone_are_exactly_the_two_log_outs(client, db):
    # Any other public POST is never requested as a page, so it has to be named here and justified (#70, #76).
    assert {entry.name for path, entry in routes_of(PUBLIC) if client.get(path).status_code == 405} == PUBLIC_POSTS


def test_every_querying_exception_is_still_a_public_page():
    assert QUERYING_PUBLIC_PAGES <= {entry.name for _, entry in routes_of(PUBLIC)}


# The forced change after a reset never reads the session on a public page either (#80).
@pytest.mark.parametrize("visitor", [anonymous, with_stale_sessions, signed_in_as_a_voter, signed_in_as_a_voter_who_must_change_their_password, signed_in_as_the_admin])
@pytest.mark.parametrize("path", PUBLIC_PAGES_THAT_MUST_NOT_QUERY)
def test_every_public_page_renders_with_no_database_queries(client, db, django_assert_num_queries, visitor, path):
    browser = visitor(client)

    with django_assert_num_queries(0):
        response = browser.get(path)

    assert response.status_code == 200


@pytest.mark.parametrize("visitor", [anonymous, with_stale_sessions, signed_in_as_the_admin])
@pytest.mark.parametrize("path", [path for path, _ in routes_of(VOTER)])
def test_every_voter_route_sends_a_visitor_without_a_voter_session_to_login(client, db, visitor, path):
    response = visitor(client).get(path)

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login/?next=")


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("visitor", [anonymous, with_stale_sessions, signed_in_as_a_voter])
@pytest.mark.parametrize("path", [path for path, _ in routes_of(ADMIN)])
def test_every_admin_route_sends_a_visitor_without_the_admin_session_to_the_admin_login(client, db, visitor, path, method):
    response = getattr(visitor(client), method)(path)

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/console/login/?next=")


@pytest.mark.parametrize("visitor", [signed_in_as_the_admin, signed_in_as_both])
@pytest.mark.parametrize("path", [path for path, _ in pages_of(ADMIN)])
def test_every_admin_page_opens_for_the_admin_without_the_voter_header(client, db, visitor, path):
    # An admin page fills base.html's header block, which would otherwise show the voter's (#73, #76).
    response = as_a_page(visitor(client).get(path, follow=True))

    assert response.status_code == 200
    assert "voter-header" not in response.text
