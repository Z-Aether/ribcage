import pytest
from django.urls import URLResolver, get_resolver

from ribcage.identity.models import Voter

# Public pages allowed to query, by URL name: the one place an exception goes, with its ticket.
QUERYING_PUBLIC_PAGES = {
    # Scaffolding whose whole job is a write path and rows to back up; M3 removes it (#42, #47).
    "hello",
}


def routes(patterns=None, prefix="/"):
    for entry in get_resolver().url_patterns if patterns is None else patterns:
        if isinstance(entry, URLResolver):
            yield from routes(entry.url_patterns, prefix + str(entry.pattern))
        else:
            yield prefix + str(entry.pattern), entry


def public_pages():
    # Public means outside the login wall, which Django's login_not_required declares (#16).
    return [(path, entry) for path, entry in routes() if getattr(entry.callback, "login_required", True) is False]


PUBLIC_PAGES = public_pages()
PAGES_THAT_MUST_NOT_QUERY = [(path, entry) for path, entry in PUBLIC_PAGES if entry.name not in QUERYING_PUBLIC_PAGES]


def anonymous(client):
    return client


def with_a_stale_session(client):
    client.cookies["sessionid"] = "a-session-the-database-never-held"
    client.cookies["csrftoken"] = "a" * 32
    return client


def signed_in_as_a_voter(client):
    client.force_login(Voter.objects.create(display_name="Ada"))
    client.cookies["csrftoken"] = "a" * 32
    return client


@pytest.mark.parametrize("visitor", [anonymous, with_a_stale_session, signed_in_as_a_voter])
@pytest.mark.parametrize("path", [path for path, _ in PAGES_THAT_MUST_NOT_QUERY])
def test_every_public_page_renders_with_no_database_queries(client, db, django_assert_num_queries, visitor, path):
    browser = visitor(client)

    with django_assert_num_queries(0):
        response = browser.get(path)

    assert response.status_code == 200


def test_the_privacy_policy_is_found_as_a_public_page_that_must_not_query():
    assert "privacy" in [entry.name for _, entry in PAGES_THAT_MUST_NOT_QUERY]


def test_every_public_page_has_a_fixed_address_the_invariant_can_request():
    assert [path for path, entry in PUBLIC_PAGES if entry.pattern.converters] == []


def test_every_querying_exception_is_still_a_public_page():
    assert QUERYING_PUBLIC_PAGES <= {entry.name for _, entry in PUBLIC_PAGES}
