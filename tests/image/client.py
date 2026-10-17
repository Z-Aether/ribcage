import http.client
import re
import time

import pytest


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
    status, headers, page = fetch(port, "GET", "/")
    cookie = next(value for value in headers.get_all("Set-Cookie") if value.startswith("csrftoken="))
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)[1]
    return cookie.split(";")[0], token


def post_form(port, fields, cookie=None, extra_headers=None):
    body = "&".join(f"{name}={value}" for name, value in fields.items())
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Origin": f"http://127.0.0.1:{port}"}
    headers.update(extra_headers or {})
    if cookie:
        headers["Cookie"] = cookie
    return fetch(port, "POST", "/", headers, body)
