import pytest
from django.test import Client

from ribcage.hello.models import Message

HOST = "ribcage.example.org"
ORIGIN = f"https://{HOST}"
ONE_YEAR_WITH_SUBDOMAINS = "max-age=31536000; includeSubDomains"


@pytest.fixture(autouse=True)
def _deployed_hostname(settings):
    settings.ALLOWED_HOSTS = [HOST]
    settings.CSRF_TRUSTED_ORIGINS = [ORIGIN]


def through_the_proxy(**headers):
    # What the TLS-terminating proxy hands the container: the browser's Host plus the forwarded scheme.
    return {"host": HOST, "x-forwarded-proto": "https", **headers}


def test_hsts_is_sent_when_the_proxy_says_the_request_arrived_over_https(client, db):
    response = client.get("/", headers=through_the_proxy())

    assert response.headers["Strict-Transport-Security"] == ONE_YEAR_WITH_SUBDOMAINS


@pytest.mark.parametrize(
    "headers",
    [
        {"host": HOST},
        through_the_proxy(**{"x-forwarded-proto": "http"}),
        {"host": HOST, "forwarded": "proto=https"},
        {"host": HOST, "x-forwarded-ssl": "on"},
        {"host": HOST, "x-forwarded-scheme": "https"},
    ],
    ids=["plain", "forwarded-proto-http", "rfc-forwarded", "forwarded-ssl", "forwarded-scheme"],
)
def test_hsts_is_not_sent_otherwise(client, db, headers):
    response = client.get("/", headers=headers)

    assert response.status_code == 200
    assert "Strict-Transport-Security" not in response.headers


def test_plain_http_is_served_rather_than_redirected_to_https(client, db):
    response = client.get("/", headers={"host": HOST})

    assert response.status_code == 200


def a_form_post_from_the_page(text, headers):
    browser = Client(enforce_csrf_checks=True)
    token = browser.get("/", headers=through_the_proxy()).context["csrf_token"]
    return browser.post("/", {"text": text, "csrfmiddlewaretoken": token}, headers=headers)


@pytest.mark.parametrize(
    "headers",
    [
        through_the_proxy(origin=ORIGIN, referer=f"{ORIGIN}/"),
        {"host": HOST, "origin": ORIGIN, "referer": f"{ORIGIN}/"},
    ],
    ids=["through-the-proxy", "header-missing"],
)
def test_the_form_post_from_the_trusted_https_origin_succeeds_with_or_without_the_header(db, headers):
    response = a_form_post_from_the_page("From the trusted origin", headers)

    assert response.status_code == 302
    assert Message.objects.filter(text="From the trusted origin").exists()


@pytest.mark.parametrize(
    "browser_headers",
    [
        {"origin": "https://elsewhere.example", "referer": "https://elsewhere.example/"},
        {"origin": f"http://{HOST}", "referer": f"http://{HOST}/"},
        {"referer": "https://elsewhere.example/"},
    ],
    ids=["other-site", "downgraded-scheme", "other-site-referer-only"],
)
def test_a_form_post_from_an_untrusted_origin_is_refused(db, browser_headers):
    response = a_form_post_from_the_page("Cross-site", through_the_proxy(**browser_headers))

    assert response.status_code == 403
    assert not Message.objects.exists()


def how_the_app_sees(client, headers):
    request = client.get("/", headers=headers).context["request"]
    return request.META["REMOTE_ADDR"], request.get_host(), request.get_port(), request.scheme


@pytest.mark.parametrize(
    "forged",
    [
        {"x-forwarded-for": "203.0.113.9"},
        {"x-forwarded-host": "elsewhere.example"},
        {"x-forwarded-port": "8443"},
        {"x-real-ip": "203.0.113.9"},
        {"forwarded": "for=203.0.113.9;host=elsewhere.example;proto=http"},
    ],
    ids=["x-forwarded-for", "x-forwarded-host", "x-forwarded-port", "x-real-ip", "rfc-forwarded"],
)
def test_a_forged_forwarded_header_changes_nothing(client, db, forged):
    assert how_the_app_sees(client, through_the_proxy(**forged)) == how_the_app_sees(client, through_the_proxy())


def test_a_forged_forwarded_host_cannot_vouch_for_a_cross_site_post(db):
    response = a_form_post_from_the_page(
        "Cross-site",
        through_the_proxy(origin="https://elsewhere.example", **{"x-forwarded-host": "elsewhere.example"}),
    )

    assert response.status_code == 403


def test_the_csrf_cookie_is_secure_http_only_and_same_site_lax_even_without_the_header(client, db):
    cookie = client.get("/", headers={"host": HOST}).cookies["csrftoken"]

    assert cookie["secure"] is True
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"
