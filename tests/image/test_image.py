import http.client
import json
import re
import time
import uuid

import pytest

from tests.image.docker import REPO_ROOT, docker, run_docker

pytestmark = pytest.mark.slow

IMAGE = "ribcage:pytest"
PORT = 8000
FORGED_ADDRESSES = {"X-Forwarded-For": "203.0.113.77", "X-Real-IP": "198.51.100.5", "Forwarded": "for=192.0.2.9"}
# Time, request line, status, duration, and nothing else (#31).
ACCESS_LINE = re.compile(r'^\[[^\]]+\] "[A-Z]+ \S+ HTTP/1\.1" \d{3} \d+ms$')
# Every variable comes from .env.example, so a new one needs no edit here; these values suit a container.
EXAMPLE = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
ENVIRONMENT = dict(re.findall(r"^([A-Z][A-Z_]+)=(.*)$", EXAMPLE, re.MULTILINE)) | {
    "SECRET_KEY": "image-test-key-not-a-real-secret-0123456789abcdefghijklmnop",
    "DEBUG": "false",
    "ALLOWED_HOSTS": "127.0.0.1",
    "CSRF_TRUSTED_ORIGINS": "https://ribcage.example.org",
    "DATABASE_PATH": "/data/db.sqlite3",
}


@pytest.fixture(scope="module")
def image():
    docker("build", "--platform", "linux/amd64", "--tag", IMAGE, str(REPO_ROOT))
    return IMAGE


@pytest.fixture(scope="module")
def container(image, tmp_path_factory):
    env_file = tmp_path_factory.mktemp("image") / "image.env"
    env_file.write_text("".join(f"{name}={value}\n" for name, value in ENVIRONMENT.items()))
    name = f"ribcage-pytest-{uuid.uuid4().hex[:8]}"
    docker("run", "--detach", "--name", name, "--env-file", str(env_file), "--publish", f"127.0.0.1::{PORT}", image)
    try:
        # Migrating is the compose stack's job (#52); here it gives the form a table to write to.
        docker("exec", name, "python", "manage.py", "migrate", "--verbosity", "0")
        host_port = int(docker("port", name, f"{PORT}/tcp").splitlines()[0].rsplit(":", 1)[1])
        wait_until_serving(host_port)
        yield name, host_port
    finally:
        docker("rm", "--force", name)


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


def test_the_image_is_built_for_the_hosts_architecture(image):
    # The host is x86-64 (#43).
    assert docker("image", "inspect", image, "--format", "{{.Os}}/{{.Architecture}}").strip() == "linux/amd64"


def test_no_setting_is_baked_into_the_image(image):
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    settings = set(re.findall(r"^#?\s*([A-Z][A-Z_]+)=", example, re.MULTILINE))
    baked = json.loads(docker("image", "inspect", image, "--format", "{{json .Config.Env}}"))
    baked_names = {entry.split("=")[0] for entry in baked}

    assert "SECRET_KEY" in settings
    assert not settings & baked_names


def test_without_its_environment_the_image_refuses_to_start(image):
    startup = run_docker("run", "--rm", image, timeout=60)

    assert startup.returncode != 0
    assert "Set the SECRET_KEY environment variable." in startup.stderr
    assert "Listening at" not in startup.stderr


def test_the_app_runs_as_a_non_root_user(container):
    name, _ = container

    assert docker("exec", name, "id", "-u").strip() != "0"


def test_the_hello_world_page_is_served(container):
    _, port = container

    status, _, page = fetch(port, "GET", "/")

    assert status == 200
    assert "Hello World" in page


def test_static_files_are_collected_and_served_by_whitenoise(container):
    _, port = container
    stylesheet = re.search(r'href="(/static/[^"]+\.css)"', fetch(port, "GET", "/")[2])[1]

    status, headers, _ = fetch(port, "GET", stylesheet)

    assert status == 200
    assert headers["Cache-Control"] == "max-age=315360000, public, immutable"


def test_the_form_post_with_the_pages_csrf_token_is_accepted(container):
    _, port = container
    cookie, token = a_page_with_its_csrf_token(port)

    status, headers, _ = post_form(port, {"csrfmiddlewaretoken": token, "text": "Posted+inside+the+image"}, cookie)

    assert (status, headers["Location"]) == (302, "/")
    assert "Posted inside the image" in fetch(port, "GET", "/")[2]


def test_a_form_post_without_a_csrf_token_is_refused(container):
    _, port = container

    assert post_form(port, {"text": "Forged"})[0] == 403


def test_the_privacy_policy_is_rendered_from_the_file_inside_the_image(container):
    name, port = container
    marker = f"Marker {uuid.uuid4().hex}"
    docker("exec", "--user", "root", name, "sh", "-c", f"echo '{marker}' >> /app/ribcage/privacy.md")

    status, _, page = fetch(port, "GET", "/privacy/")

    assert status == 200
    assert "<h1>Privacy policy</h1>" in page
    assert marker in page


def test_the_access_log_goes_to_stdout_without_any_client_address(container):
    name, port = container
    probe = f"/?probe={uuid.uuid4().hex}"

    fetch(port, "GET", probe, FORGED_ADDRESSES)

    logs = logs_once_they_show(name, probe)
    probe_lines = [line for line in logs.stdout.splitlines() if probe in line]
    assert len(probe_lines) == 1 and ACCESS_LINE.match(probe_lines[0]), probe_lines
    assert not any(value.removeprefix("for=") in logs.stdout + logs.stderr for value in FORGED_ADDRESSES.values())


def logs_once_they_show(name, text):
    for _ in range(20):
        logs = run_docker("logs", name, timeout=60)
        if text in logs.stdout:
            return logs
        time.sleep(0.25)
    pytest.fail(f"{text} never reached the container's stdout.")


def test_a_server_error_leaves_its_traceback_on_stderr_without_any_client_address(container):
    name, port = container
    cookie, token = a_page_with_its_csrf_token(port)
    docker("exec", name, "chmod", "-R", "a-w", "/data")
    try:
        status, _, _ = post_form(port, {"csrfmiddlewaretoken": token, "text": "Unwritable"}, cookie, FORGED_ADDRESSES)
    finally:
        docker("exec", name, "chmod", "-R", "u+w", "/data")

    assert status == 500
    for _ in range(20):
        logs = run_docker("logs", name, timeout=60)
        if "Traceback" in logs.stderr:
            break
        time.sleep(0.25)
    assert "Traceback" in logs.stderr and "readonly database" in logs.stderr
    assert not any(value.removeprefix("for=") in logs.stdout + logs.stderr for value in FORGED_ADDRESSES.values())
