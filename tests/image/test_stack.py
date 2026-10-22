import json
import re
import sqlite3
from contextlib import closing

import pytest

from ribcage.operations.backup import describe, row_counts
from tests.image.client import (
    CREATE_THE_VOTER,
    LOGIN,
    SIGNED_IN_AS_THE_VOTER,
    download_a_backup,
    fetch,
    phase_page,
    session_of,
    sign_in,
    sign_in_as_the_admin,
    upload_a_backup,
    wait_until_serving,
)
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
        stack("exec", "ribcage", *CREATE_THE_VOTER)
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
    status, _, page = fetch(hosted_stack.port(), "GET", LOGIN)

    assert status == 200
    assert "Log in" in page


def test_the_log_is_json_file_with_a_size_and_file_count_cap(hosted_stack):
    log = hosted_stack.inspect(".HostConfig.LogConfig")

    assert log["Type"] == "json-file"
    assert set(log["Config"]) == {"max-size", "max-file"}


def test_the_database_on_the_volume_is_in_wal_mode(hosted_stack):
    assert hosted_stack.journal_mode() == "wal"


def test_the_local_stack_migrates_a_fresh_volume_and_serves_the_login_page(local_stack):
    status, _, page = fetch(local_stack.port(), "GET", LOGIN)

    assert status == 200
    assert "Log in" in page


def test_the_local_stack_accepts_the_form_post_with_the_pages_csrf_token(local_stack):
    port = local_stack.port()

    status, headers, _ = sign_in(port)

    assert (status, headers["Location"]) == (302, "/")
    assert SIGNED_IN_AS_THE_VOTER in phase_page(port, session_of(headers))[2]


def test_a_written_row_survives_down_then_up(local_stack):
    # Signing in writes the session row (#70).
    session = session_of(sign_in(local_stack.port())[1])

    local_stack("down")
    local_stack("up", "--detach", "--wait")
    wait_until_serving(local_stack.port())

    assert SIGNED_IN_AS_THE_VOTER in phase_page(local_stack.port(), session)[2]


def test_a_code_made_in_the_apps_container_downloads_its_backup_once_from_the_admin_side(local_stack, tmp_path):
    offering = local_stack("exec", "ribcage", "python", "manage.py", "backupcode", "download")
    offered_counts = re.search(r"^Offered backup-\d{8}-\d{6}\.sqlite3: (.*)\.$", offering, re.M)[1]
    code = code_in(offering)
    admin = sign_in_as_the_admin(local_stack.port(), EXAMPLE["ADMIN_PASSWORD"])

    status, headers, content = download_a_backup(local_stack.port(), admin, code)

    assert (status, headers["Cache-Control"]) == (200, "no-store")
    downloaded = tmp_path / "downloaded.sqlite3"
    downloaded.write_bytes(content)
    assert describe(row_counts(downloaded)) == offered_counts
    assert local_stack("exec", "ribcage", "ls", "-A", "/data/backup-offer").strip() == ""
    assert download_a_backup(local_stack.port(), admin, code)[1].get("Content-Disposition") is None


def code_in(offering):
    return re.search(r"^Code: (\w+)$", offering, re.M)[1]


def backup_command(*arguments):
    return ["exec", "backup", "python", "-m", "ribcage.operations.backup", *arguments]


def test_a_backup_uploaded_from_the_admin_side_restores_in_the_sidecar_from_the_data_volume(local_stack, tmp_path):
    admin = sign_in_as_the_admin(local_stack.port(), EXAMPLE["ADMIN_PASSWORD"])
    offering = local_stack("exec", "ribcage", "python", "manage.py", "backupcode", "download")
    pulled = tmp_path / "pulled.sqlite3"
    pulled.write_bytes(download_a_backup(local_stack.port(), admin, code_in(offering))[2])
    # A table the stack lacks marks the restore; its size, past Django's in-memory limit, takes a temporary file (#81).
    with closing(sqlite3.connect(pulled)) as connection:
        connection.execute("CREATE TABLE ballast (b BLOB)")
        connection.execute("INSERT INTO ballast VALUES (randomblob(3 * 1024 * 1024))")
        connection.commit()
    upload_code = code_in(local_stack("exec", "ribcage", "python", "manage.py", "backupcode", "upload"))

    status, _, page = upload_a_backup(local_stack.port(), admin, upload_code, pulled)

    assert status == 200
    name = re.search(r"Kept <code>(backup-\d{8}-\d{6}\.sqlite3)</code>", page)[1]
    assert f"restore {name} --backups /data" in page
    local_stack("stop", "ribcage")
    restored = local_stack(*backup_command("restore", name, "--backups", "/data"))
    local_stack("start", "ribcage")
    wait_until_serving(local_stack.port())
    assert f"Restored {name}: {describe(row_counts(pulled))}." in restored
    assert local_stack(*backup_command("counts")).strip() == describe(row_counts(pulled))
    local_stack("exec", "backup", "rm", f"/data/{name}")
    assert local_stack("exec", "ribcage", "ls", "-A", "/data").split() == ["backup-offer", "db.sqlite3", "db.sqlite3-shm", "db.sqlite3-wal"]


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

