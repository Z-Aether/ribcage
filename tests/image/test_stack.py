import json

import pytest

from tests.image.client import a_page_with_its_csrf_token, fetch, post_form, wait_until_serving
from tests.image.docker import REPO_ROOT
from tests.image.stack import EXAMPLE, LOCALLY_ON_THE_IMAGE_UNDER_TEST, ON_THE_IMAGE_UNDER_TEST, Stack, override

pytestmark = pytest.mark.slow

# The host port the proxy forwards to, which the base file publishes on every interface (#54).
PROXY_PORT = 8080


@pytest.fixture(scope="module")
def local_stack(image, tmp_path_factory):
    directory = tmp_path_factory.mktemp("local-stack")
    files = [REPO_ROOT / "compose.yaml", REPO_ROOT / "compose.local.yaml"]
    files.append(override(directory, "test.yaml", LOCALLY_ON_THE_IMAGE_UNDER_TEST))
    stack = Stack(directory, files, dict(EXAMPLE))
    try:
        stack("up", "--detach", "--wait")
        wait_until_serving(stack.port())
        yield stack
    finally:
        stack.run("down", "--volumes")


@pytest.fixture(scope="module")
def hosted_stack(image, tmp_path_factory):
    # The base file alone, as Komodo runs it, but for the image and the host port.
    directory = tmp_path_factory.mktemp("hosted-stack")
    files = [REPO_ROOT / "compose.yaml", override(directory, "test.yaml", ON_THE_IMAGE_UNDER_TEST)]
    stack = Stack(directory, files, dict(EXAMPLE))
    try:
        stack("up", "--detach", "--wait")
        wait_until_serving(stack.port())
        yield stack
    finally:
        stack.run("down", "--volumes")


def test_the_running_stack_publishes_the_app_on_the_hosts_loopback_alone(hosted_stack):
    bindings = hosted_stack.inspect(".HostConfig.PortBindings")

    assert list(bindings) == ["8000/tcp"]
    assert [binding["HostIp"] for binding in bindings["8000/tcp"]] == ["127.0.0.1"]


def test_the_proxy_on_the_host_reaches_the_app_at_its_port(hosted_stack):
    status, _, page = fetch(hosted_stack.port(), "GET", "/")

    assert status == 200
    assert "Hello World" in page


def test_the_log_is_json_file_with_a_size_and_file_count_cap(hosted_stack):
    log = hosted_stack.inspect(".HostConfig.LogConfig")

    assert log["Type"] == "json-file"
    assert set(log["Config"]) == {"max-size", "max-file"}


def test_the_database_on_the_volume_is_in_wal_mode(hosted_stack):
    assert hosted_stack.journal_mode() == "wal"


def test_the_local_stack_migrates_a_fresh_volume_and_serves_hello_world(local_stack):
    status, _, page = fetch(local_stack.port(), "GET", "/")

    assert status == 200
    assert "Hello World" in page


def test_the_local_stack_accepts_the_form_post_with_the_pages_csrf_token(local_stack):
    port = local_stack.port()
    cookie, token = a_page_with_its_csrf_token(port)

    status, headers, _ = post_form(port, {"csrfmiddlewaretoken": token, "text": "Posted+through+the+stack"}, cookie)

    assert (status, headers["Location"]) == (302, "/")
    assert "Posted through the stack" in fetch(port, "GET", "/")[2]


def test_a_written_row_survives_down_then_up(local_stack):
    port = local_stack.port()
    cookie, token = a_page_with_its_csrf_token(port)
    post_form(port, {"csrfmiddlewaretoken": token, "text": "Kept+on+the+volume"}, cookie)

    local_stack("down")
    local_stack("up", "--detach", "--wait")
    wait_until_serving(local_stack.port())

    assert "Kept on the volume" in fetch(local_stack.port(), "GET", "/")[2]


def test_an_empty_secret_stops_startup_naming_it(image, tmp_path):
    files = [REPO_ROOT / "compose.yaml", REPO_ROOT / "compose.local.yaml"]
    files.append(override(tmp_path, "test.yaml", LOCALLY_ON_THE_IMAGE_UNDER_TEST))
    stack = Stack(tmp_path, files, EXAMPLE | {"SECRET_KEY": ""})
    try:
        startup = stack.run("run", "--rm", "--no-TTY", "ribcage", timeout=120)
    finally:
        stack.run("down", "--volumes")

    assert startup.returncode != 0
    assert "Set the SECRET_KEY environment variable." in startup.stderr
    assert "Listening at" not in startup.stdout + startup.stderr


def published_ports(stack):
    resolved = json.loads(stack("config", "--format", "json"))
    return [(port.get("host_ip", ""), port["published"], port["target"]) for port in resolved["services"]["ribcage"]["ports"]]


def test_compose_resolves_the_base_file_to_the_proxys_port(tmp_path):
    stack = Stack(tmp_path, [REPO_ROOT / "compose.yaml"], dict(EXAMPLE))

    assert published_ports(stack) == [("", str(PROXY_PORT), 8000)]


def test_compose_resolves_the_local_stack_to_loopback_at_8000_in_place_of_the_proxys_port(tmp_path):
    stack = Stack(tmp_path, [REPO_ROOT / "compose.yaml", REPO_ROOT / "compose.local.yaml"], dict(EXAMPLE))

    assert published_ports(stack) == [("127.0.0.1", "8000", 8000)]

