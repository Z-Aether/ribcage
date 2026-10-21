"""Every route sorted into public, voter or admin by the marks on its view, for the tests that hold each kind to its rules (#76)."""

import re

import pytest
from django.urls import URLResolver, get_resolver

PUBLIC = "public"
VOTER = "voter"
ADMIN = "admin"

# Public routes that answer POST alone: each log out, outside the walls so a stale tab's lands on a login (#70, #76).
PUBLIC_POSTS = {"logout", "admin_logout"}

# A value each built-in converter accepts, so a route with one is requested at an address it answers (#76).
SAMPLES = {"int": "1", "str": "x", "slug": "x", "path": "x", "uuid": "00000000-0000-0000-0000-000000000000"}
PARAMETER = re.compile(r"<(?:(?P<converter>[^>:]+):)?(?P<parameter>[^>]+)>")


def route_templates(patterns=None, prefix="/"):
    for entry in get_resolver().url_patterns if patterns is None else patterns:
        if isinstance(entry, URLResolver):
            yield from route_templates(entry.url_patterns, prefix + str(entry.pattern))
        else:
            yield prefix + str(entry.pattern), entry


def address(template):
    return PARAMETER.sub(lambda parameter: SAMPLES[parameter["converter"] or "str"], template)


def routes():
    for template, entry in route_templates():
        yield address(template), entry


def kind(entry):
    """PUBLIC, VOTER or ADMIN, or None for a view marked as both voter-walled and admin-walled."""
    # login_not_required takes a view outside the voter wall (#16); admin_required also puts it behind the admin's.
    outside_the_voter_wall = getattr(entry.callback, "login_required", True) is False
    if getattr(entry.callback, "admin_required", False):
        return ADMIN if outside_the_voter_wall else None
    return PUBLIC if outside_the_voter_wall else VOTER


def routes_of(route_kind):
    return [(path, entry) for path, entry in routes() if kind(entry) == route_kind]


def pages_of(route_kind):
    # A page with an id is held by its own ticket's tests against a real row (#76).
    return [(template, entry) for template, entry in route_templates() if kind(entry) == route_kind and "<" not in template]


def public_pages():
    return [(path, entry) for path, entry in routes_of(PUBLIC) if entry.name not in PUBLIC_POSTS]


def as_a_page(response):
    """The response to a GET, or the test skipped where the route answers POST alone and so is no page."""
    if response.status_code == 405:
        pytest.skip("answers POST alone, so is no page")
    return response
