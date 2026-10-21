import json
import re
import time
import uuid

import pytest

from tests.image.client import (
    CREATE_THE_VOTER,
    LOGIN,
    fetch,
    home_page,
    post_form,
    session_of,
    sign_in,
    wait_until_serving,
)
from tests.image.docker import REPO_ROOT, docker, run_docker

pytestmark = pytest.mark.slow

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
def container(image, tmp_path_factory):
    env_file = tmp_path_factory.mktemp("image") / "image.env"
    env_file.write_text("".join(f"{name}={value}\n" for name, value in ENVIRONMENT.items()))
    name = f"ribcage-pytest-{uuid.uuid4().hex[:8]}"
    docker("run", "--detach", "--name", name, "--env-file", str(env_file), "--publish", f"127.0.0.1::{PORT}", image)
    try:
        host_port = int(docker("port", name, f"{PORT}/tcp").splitlines()[0].rsplit(":", 1)[1])
        wait_until_serving(host_port)
        docker("exec", name, *CREATE_THE_VOTER)
        yield name, host_port
    finally:
        docker("rm", "--force", name)


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


def test_the_container_migrates_a_fresh_database_before_serving(container):
    name, _ = container

    assert run_docker("exec", name, "python", "manage.py", "migrate", "--check").returncode == 0


def test_gunicorn_takes_over_as_the_containers_first_process(container):
    # Docker's stop signal reaches PID 1, so the migrating shell must have exec'd gunicorn.
    name, _ = container

    assert "gunicorn" in docker("exec", name, "cat", "/proc/1/cmdline")


def test_the_login_page_is_served_and_walls_the_rest(container):
    _, port = container

    status, _, page = fetch(port, "GET", LOGIN)

    assert status == 200
    assert "Log in" in page
    assert fetch(port, "GET", "/")[1]["Location"] == "/login/?next=/"


def test_a_plain_request_gets_hsts_as_the_image_takes_every_request_as_https(container):
    _, port = container

    _, headers, _ = fetch(port, "GET", "/", {"X-Forwarded-Proto": "http"})

    assert headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


def test_static_files_are_collected_and_served_by_whitenoise(container):
    _, port = container
    stylesheet = re.search(r'href="(/static/[^"]+\.css)"', fetch(port, "GET", LOGIN)[2])[1]

    status, headers, _ = fetch(port, "GET", stylesheet)

    assert status == 200
    assert headers["Cache-Control"] == "max-age=315360000, public, immutable"


def test_the_form_post_with_the_pages_csrf_token_is_accepted(container):
    _, port = container

    status, headers, _ = sign_in(port)

    assert (status, headers["Location"]) == (302, "/")
    assert "Signed in as Sam" in home_page(port, session_of(headers))[2]


def test_a_form_post_without_a_csrf_token_is_refused(container):
    _, port = container

    assert post_form(port, {"username": "Sam", "password": "Forged"})[0] == 403


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
    docker("exec", name, "chmod", "-R", "a-w", "/data")
    try:
        # Signing in writes the session row, which the read-only database refuses.
        status, _, _ = sign_in(port, FORGED_ADDRESSES)
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
