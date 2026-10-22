import http.client
import re
import time
import uuid

import pytest

# Public, so the page answers rather than the wall's redirect; its submit is the image's form POST (#70).
LOGIN = "/login/"
ADMIN_LOGIN = "/console/login/"
# Its code is made in the app's container, by the command an admin runs in Komodo's terminal (#68).
BACKUP_PAGE = "/console/backup/"
# Its form posts here, from the same page, with a code made by the same command (#81).
BACKUP_UPLOAD = "/console/backup/upload/"
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
    return cookie_named(headers, "csrftoken"), csrf_token_in(page)


def csrf_token_in(page):
    return re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)[1]


def form_post(port, fields, cookie=None, extra_headers=None):
    """The headers and body of a form's POST."""
    body = "&".join(f"{name}={value}" for name, value in fields.items())
    # As through the proxy, where the page is https: the image runs with DEBUG off and takes every request as HTTPS (#54).
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Origin": f"https://127.0.0.1:{port}"}
    headers.update(extra_headers or {})
    if cookie:
        headers["Cookie"] = cookie
    return headers, body


def post_form(port, fields, cookie=None, extra_headers=None, path=LOGIN):
    return fetch(port, "POST", path, *form_post(port, fields, cookie, extra_headers))


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


def backup_pages_csrf_token(port, admin_cookies):
    _, _, page = fetch(port, "GET", BACKUP_PAGE, {"Cookie": admin_cookies})
    return csrf_token_in(page)


def download_a_backup(port, admin_cookies, code):
    token = backup_pages_csrf_token(port, admin_cookies)
    return fetch_bytes(port, "POST", BACKUP_PAGE, *form_post(port, {"csrfmiddlewaretoken": token, "code": code}, admin_cookies))


def upload_a_backup(port, admin_cookies, code, backup_file):
    boundary = uuid.uuid4().hex
    fields = {"csrfmiddlewaretoken": backup_pages_csrf_token(port, admin_cookies), "code": code}
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode() for name, value in fields.items()]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="backup"; filename="{backup_file.name}"\r\n\r\n'.encode())
    parts += [backup_file.read_bytes(), f"\r\n--{boundary}--\r\n".encode()]
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", "Origin": f"https://127.0.0.1:{port}", "Cookie": admin_cookies}
    return fetch(port, "POST", BACKUP_UPLOAD, headers, b"".join(parts))


def home_page(port, session):
    return fetch(port, "GET", "/", {"Cookie": session})
