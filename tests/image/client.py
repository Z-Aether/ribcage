import http.client
import re
import time

import pytest

# Public, so the page answers rather than the wall's redirect; its submit is the image's form POST (#70).
LOGIN = "/login/"
ADMIN_LOGIN = "/console/login/"
# Its code is made in the app's container, by the command an admin runs in Komodo's terminal (#68).
BACKUP_PAGE = "/console/backup/"
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


def fetch_bytes(port, method, path, headers=None, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.headers, response.read()
    finally:
        connection.close()


def fetch(port, method, path, headers=None, body=None):
    status, headers, content = fetch_bytes(port, method, path, headers, body)
    return status, headers, content.decode()


def cookie_named(headers, name):
    return next(value for value in headers.get_all("Set-Cookie") if value.startswith(f"{name}=")).split(";")[0]


def a_page_with_its_csrf_token(port, path=LOGIN):
    status, headers, page = fetch(port, "GET", path)
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)[1]
    return cookie_named(headers, "csrftoken"), token


def post_form(port, fields, cookie=None, extra_headers=None, path=LOGIN, fetcher=fetch):
    body = "&".join(f"{name}={value}" for name, value in fields.items())
    # As through the proxy, where the page is https: the image runs with DEBUG off and takes every request as HTTPS (#54).
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Origin": f"https://127.0.0.1:{port}"}
    headers.update(extra_headers or {})
    if cookie:
        headers["Cookie"] = cookie
    return fetcher(port, "POST", path, headers, body)


def sign_in(port, extra_headers=None):
    cookie, token = a_page_with_its_csrf_token(port)
    fields = {"csrfmiddlewaretoken": token, "username": VOTER, "password": PASSWORD}
    return post_form(port, fields, cookie, extra_headers)


def session_of(headers):
    return cookie_named(headers, "sessionid")


def sign_in_as_the_admin(port, password):
    """The cookies of an admin session, its CSRF cookie among them."""
    csrf_cookie, token = a_page_with_its_csrf_token(port, ADMIN_LOGIN)
    _, headers, _ = post_form(port, {"csrfmiddlewaretoken": token, "password": password}, csrf_cookie, path=ADMIN_LOGIN)
    return f"{csrf_cookie}; {cookie_named(headers, 'adminsessionid')}"


def download_a_backup(port, admin_cookies, code):
    _, _, page = fetch(port, "GET", BACKUP_PAGE, {"Cookie": admin_cookies})
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)[1]
    return post_form(port, {"csrfmiddlewaretoken": token, "code": code}, admin_cookies, path=BACKUP_PAGE, fetcher=fetch_bytes)


def home_page(port, session):
    return fetch(port, "GET", "/", {"Cookie": session})
