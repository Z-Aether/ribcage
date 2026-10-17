import json

import pytest

from tests.image.client import a_page_with_its_csrf_token, fetch, post_form, wait_until_serving
from tests.image.conftest import IMAGE
from tests.image.docker import REPO_ROOT, docker, run_docker
from tests.image.stack import EXAMPLE, LOCALLY_ON_THE_IMAGE_UNDER_TEST, ON_THE_IMAGE_UNDER_TEST, Stack, override

pytestmark = pytest.mark.slow

# What the proxy does: reach the app by its alias on the shared network, naming an allowed host.
THROUGH_THE_PROXY_NETWORK = """
import http.client, sys, time
for _ in range(120):
    try:
        connection = http.client.HTTPConnection("ribcage", 8000, timeout=5)
        connection.request("GET", "/", headers={"Host": "localhost"})
        response = connection.getresponse()
        print(response.status, response.read().decode())
        sys.exit()
    except OSError:
        time.sleep(0.5)
sys.exit("The app never answered on the proxy network.")
"""


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
    # The base file alone, as Komodo runs it, on an external network standing in for the proxy's.
    directory = tmp_path_factory.mktemp("hosted-stack")
    files = [REPO_ROOT / "compose.yaml", override(directory, "test.yaml", ON_THE_IMAGE_UNDER_TEST)]
    stack = Stack(directory, files, dict(EXAMPLE))
    docker("network", "create", stack.network)
    try:
        stack("up", "--detach", "--wait")
        yield stack
    finally:
        stack.run("down", "--volumes")
        run_docker("network", "rm", stack.network)


def through_the_proxy_network(stack):
    return docker("run", "--rm", "--network", stack.network, IMAGE, "python", "-c", THROUGH_THE_PROXY_NETWORK)


def test_the_base_file_publishes_no_host_port(hosted_stack):
    assert hosted_stack.inspect(".HostConfig.PortBindings") in ({}, None)
    assert hosted_stack.inspect(".NetworkSettings.Ports") == {"8000/tcp": None}


def test_the_app_is_on_the_proxy_network_alone_under_its_alias(hosted_stack):
    networks = hosted_stack.inspect(".NetworkSettings.Networks")

    assert list(networks) == [hosted_stack.network]
    assert "ribcage" in networks[hosted_stack.network]["DNSNames"]


def test_the_proxy_reaches_the_app_by_its_alias_and_port(hosted_stack):
    assert through_the_proxy_network(hosted_stack).startswith("200 ")


def test_the_log_is_json_file_with_a_size_and_file_count_cap(hosted_stack):
    log = hosted_stack.inspect(".HostConfig.LogConfig")

    assert log["Type"] == "json-file"
    assert set(log["Config"]) == {"max-size", "max-file"}


def test_the_database_on_the_volume_is_in_wal_mode(hosted_stack):
    through_the_proxy_network(hosted_stack)

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


def test_compose_resolves_the_base_file_with_the_proxy_network_named(tmp_path):
    stack = Stack(tmp_path, [REPO_ROOT / "compose.yaml"], dict(EXAMPLE))

    resolved = json.loads(stack("config", "--format", "json"))

    assert (resolved["networks"]["proxy"]["name"], resolved["networks"]["proxy"]["external"]) == (stack.network, True)


def test_compose_refuses_the_base_file_without_the_proxy_network(tmp_path):
    stack = Stack(tmp_path, [REPO_ROOT / "compose.yaml"], dict(EXAMPLE))
    stack.arguments[stack.arguments.index("--env-file") + 1] = str(override(tmp_path, "empty.env", ""))

    refusal = stack.run("config")

    assert refusal.returncode != 0
    assert "Set PROXY_NETWORK" in refusal.stderr

