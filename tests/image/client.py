import http.client
import re
import time

import pytest

# Public, so the page answers rather than the wall's redirect; its submit is the image's form POST (#70).
LOGIN = "/login/"
VOTER = "Sam"
PASSWORD = "popcorn-before-midnight"
# The voter header names whoever is signed in, on every walled page (#73).
SIGNED_IN_AS_THE_VOTER = f'<summary class="voter-menu__name">{VOTER}</summary>'
# Run inside the app's container: no registration yet, so the voter is made in its shell (#70).
CREATE_THE_VOTER = [
    "python",
    "manage.py",
    "shell",
    "--command",
    f"from ribcage.identity.models import Voter; Voter.objects.create_voter({VOTER!r}, {PASSWORD!r})",
]


def wait_until_serving(port):
    for _ in range(60):
        try:
            fetch(port, "GET", "/static/vendor/vendored.toml")
            return
        except OSError:
            time.sleep(0.5)
    pytest.fail("The container never answered.")


def fetch(port, method, path, headers=None, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.headers, response.read().decode()
    finally:
        connection.close()


def a_page_with_its_csrf_token(port):
    status, headers, page = fetch(port, "GET", LOGIN)
    cookie = next(value for value in headers.get_all("Set-Cookie") if value.startswith("csrftoken="))
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)[1]
    return cookie.split(";")[0], token


def post_form(port, fields, cookie=None, extra_headers=None):
    body = "&".join(f"{name}={value}" for name, value in fields.items())
    # As through the proxy, where the page is https: the image runs with DEBUG off and takes every request as HTTPS (#54).
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Origin": f"https://127.0.0.1:{port}"}
    headers.update(extra_headers or {})
    if cookie:
        headers["Cookie"] = cookie
    return fetch(port, "POST", LOGIN, headers, body)


def sign_in(port, extra_headers=None):
    cookie, token = a_page_with_its_csrf_token(port)
    fields = {"csrfmiddlewaretoken": token, "username": VOTER, "password": PASSWORD}
    return post_form(port, fields, cookie, extra_headers)


def session_of(headers):
    return next(value for value in headers.get_all("Set-Cookie") if value.startswith("sessionid=")).split(";")[0]


def home_page(port, session):
    return fetch(port, "GET", "/", {"Cookie": session})
