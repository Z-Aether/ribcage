import html
import json
import re

import pytest
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse
from django.test import Client
from django.urls import path
from django.views.decorators.http import require_POST

import ribcage.urls
from ribcage.identity.models import Voter
from tests.http.test_admin_login import sign_in_as_the_admin
from tests.http.test_proxy_boundary import HOST, ORIGIN, at_the_host


@login_not_required
@require_POST
def an_htmx_action(request):
    return HttpResponse("posted")


# A test-only action, so no production route exists for the test's sake; the app's own routes come with it.
urlpatterns = [*ribcage.urls.urlpatterns, path("test-only/htmx-action/", an_htmx_action)]
pytestmark = pytest.mark.urls(__name__)


@pytest.fixture(autouse=True)
def _deployed_hostname(settings):
    # Same-origin, as htmx posts from the page it is on; no trusted origin is needed for it.
    settings.ALLOWED_HOSTS = [HOST]
    settings.CSRF_TRUSTED_ORIGINS = []


def as_a_voter(signing_in):
    signing_in.force_login(Voter.objects.create_voter("Ada"))
    return "/"


def as_the_admin(signing_in):
    sign_in_as_the_admin(signing_in, headers=at_the_host())
    return "/console/films/"


def a_browser(signed_in):
    # Signed in without the CSRF check, then held to it like a real browser from there on.
    signing_in = Client()
    walled_page = signed_in(signing_in)
    browser = Client(enforce_csrf_checks=True)
    browser.cookies = signing_in.cookies
    return browser, walled_page


def htmx_headers(page):
    return json.loads(html.unescape(re.search(r"<body [^>]*hx-headers='([^']+)'", page)[1]))


@pytest.mark.parametrize("signed_in", [as_a_voter, as_the_admin])
def test_an_htmx_post_from_a_walled_page_passes_csrf(db, signed_in):
    browser, walled_page = a_browser(signed_in)
    page = browser.get(walled_page, headers=at_the_host())
    assert page.status_code == 200

    headers = at_the_host(**{"HX-Request": "true", "origin": ORIGIN}, **htmx_headers(page.text))
    response = browser.post("/test-only/htmx-action/", headers=headers)

    assert (response.status_code, response.text) == (200, "posted")


def test_the_same_htmx_post_without_the_pages_token_is_refused(db):
    browser, walled_page = a_browser(as_a_voter)
    browser.get(walled_page, headers=at_the_host())

    response = browser.post("/test-only/htmx-action/", headers=at_the_host(**{"HX-Request": "true", "origin": ORIGIN}))

    assert response.status_code == 403
