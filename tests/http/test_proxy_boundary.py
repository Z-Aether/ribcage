import os

import pytest
from django.test import Client

from ribcage.hello.models import Message

HOST = "ribcage.example.org"
ORIGIN = f"https://{HOST}"
ONE_YEAR_WITH_SUBDOMAINS = "max-age=31536000; includeSubDomains"
WHATEVER_THE_PROXY_SAYS = [
    {},
    {"x-forwarded-proto": "http"},
    {"x-forwarded-proto": "https"},
    {"forwarded": "proto=http"},
    {"x-forwarded-ssl": "off"},
    {"x-forwarded-scheme": "http"},
]
WHATEVER_THE_PROXY_SAYS_IDS = ["nothing", "proto-http", "proto-https", "rfc-forwarded", "forwarded-ssl", "scheme"]


@pytest.fixture(autouse=True)
def _deployed_hostname(settings):
    settings.ALLOWED_HOSTS = [HOST]
    settings.CSRF_TRUSTED_ORIGINS = [ORIGIN]


def at_the_host(**headers):
    return {"host": HOST, **headers}


@pytest.mark.parametrize("forwarded", WHATEVER_THE_PROXY_SAYS, ids=WHATEVER_THE_PROXY_SAYS_IDS)
def test_outside_debug_every_request_is_https_whatever_the_proxy_says(client, db, forwarded):
    response = client.get("/", headers=at_the_host(**forwarded))

    assert response.context["request"].scheme == "https"
    assert response.headers["Strict-Transport-Security"] == ONE_YEAR_WITH_SUBDOMAINS


@pytest.mark.parametrize("forwarded", WHATEVER_THE_PROXY_SAYS, ids=WHATEVER_THE_PROXY_SAYS_IDS)
def test_with_debug_on_every_request_stays_plain_http(client, db, settings, forwarded):
    settings.DEBUG = True

    response = client.get("/", headers=at_the_host(**forwarded))

    assert response.context["request"].scheme == "http"
    assert "Strict-Transport-Security" not in response.headers


def test_plain_http_is_served_rather_than_redirected_to_https(client, db):
    response = client.get("/", headers=at_the_host())

    assert response.status_code == 200


def a_form_post_from_the_page(text, headers):
    browser = Client(enforce_csrf_checks=True)
    token = browser.get("/", headers=at_the_host()).context["csrf_token"]
    return browser.post("/", {"text": text, "csrfmiddlewaretoken": token}, headers=headers)


@pytest.mark.parametrize(
    "browser_headers",
    [
        {"origin": ORIGIN, "referer": f"{ORIGIN}/"},
        {"referer": f"{ORIGIN}/"},
    ],
    ids=["origin", "referer-only"],
)
def test_the_form_post_from_the_trusted_https_origin_succeeds(db, browser_headers):
    response = a_form_post_from_the_page("From the trusted origin", at_the_host(**browser_headers))

    assert response.status_code == 302
    assert Message.objects.filter(text="From the trusted origin").exists()


@pytest.mark.parametrize(
    "browser_headers",
    [
        {"origin": "https://elsewhere.example", "referer": "https://elsewhere.example/"},
        {"origin": f"http://{HOST}", "referer": f"http://{HOST}/"},
        {"referer": "https://elsewhere.example/"},
        {"referer": f"http://{HOST}/"},
        {},
    ],
    ids=["other-site", "downgraded-scheme", "other-site-referer-only", "downgraded-referer-only", "neither"],
)
def test_a_form_post_from_an_untrusted_origin_is_refused(db, browser_headers):
    response = a_form_post_from_the_page("Cross-site", at_the_host(**browser_headers))

    assert response.status_code == 403
    assert not Message.objects.exists()


def test_a_form_post_from_the_local_plain_http_origin_succeeds_with_the_example_trusted_origins(db, settings):
    # Outside DEBUG a plain-http origin no longer matches the host, so a local run posts only through this list (#54).
    settings.ALLOWED_HOSTS = ["127.0.0.1"]
    settings.CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ["CSRF_TRUSTED_ORIGINS"].split(",")]
    local = {"host": "127.0.0.1:8000"}
    browser = Client(enforce_csrf_checks=True)
    token = browser.get("/", headers=local).context["csrf_token"]

    response = browser.post(
        "/", {"text": "From the local stack", "csrfmiddlewaretoken": token}, headers=local | {"origin": "http://127.0.0.1:8000"}
    )

    assert response.status_code == 302


def how_the_app_sees(client, headers):
    request = client.get("/", headers=headers).context["request"]
    return request.META["REMOTE_ADDR"], request.get_host(), request.get_port(), request.scheme


@pytest.mark.parametrize(
    "forged",
    [
        {"x-forwarded-for": "203.0.113.9"},
        {"x-forwarded-host": "elsewhere.example"},
        {"x-forwarded-port": "8443"},
        {"x-forwarded-proto": "http"},
        {"x-real-ip": "203.0.113.9"},
        {"forwarded": "for=203.0.113.9;host=elsewhere.example;proto=http"},
    ],
    ids=["x-forwarded-for", "x-forwarded-host", "x-forwarded-port", "x-forwarded-proto", "x-real-ip", "rfc-forwarded"],
)
def test_a_forged_forwarded_header_changes_nothing(client, db, forged):
    assert how_the_app_sees(client, at_the_host(**forged)) == how_the_app_sees(client, at_the_host())


def test_a_forged_forwarded_host_cannot_vouch_for_a_cross_site_post(db):
    response = a_form_post_from_the_page(
        "Cross-site",
        at_the_host(origin="https://elsewhere.example", **{"x-forwarded-host": "elsewhere.example"}),
    )

    assert response.status_code == 403


def test_the_csrf_cookie_is_secure_http_only_and_same_site_lax(client, db):
    cookie = client.get("/", headers=at_the_host()).cookies["csrftoken"]

    assert cookie["secure"] is True
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"
