import time

import pytest

from ribcage.operations.backup import KEPT_BACKUPS, is_backup, row_counts
from tests.image.client import (
    CREATE_THE_VOTER,
    SIGNED_IN_AS_THE_VOTER,
    home_page,
    session_of,
    sign_in,
    wait_until_serving,
)
from tests.image.docker import REPO_ROOT
from tests.image.stack import EXAMPLE, LOCALLY_ON_THE_IMAGE_UNDER_TEST, Stack, override

pytestmark = pytest.mark.slow

ANNOUNCEMENT = "Next backup at "
# Named a day apart in 2000, so each is older than any backup the sidecar takes.
PLANTED = [f"backup-200001{day:02}-040000.sqlite3" for day in range(1, KEPT_BACKUPS + 2)]


def local_stack_in(directory):
    files = [REPO_ROOT / "compose.yaml", REPO_ROOT / "compose.local.yaml"]
    files.append(override(directory, "test.yaml", LOCALLY_ON_THE_IMAGE_UNDER_TEST))
    return Stack(directory, files, dict(EXAMPLE))


@pytest.fixture(scope="module")
def stack(image, tmp_path_factory):
    stack = local_stack_in(tmp_path_factory.mktemp("sidecar-stack"))
    try:
        stack("up", "--detach", "--wait")
        wait_until_serving(stack.port())
        stack("exec", "ribcage", *CREATE_THE_VOTER)
        yield stack
    finally:
        stack.run("down", "--volumes")


def sidecar(stack, *arguments):
    return stack("exec", "backup", "python", "-m", "ribcage.operations.backup", *arguments)


def backups_on_the_volume(stack):
    return sorted(stack("exec", "backup", "ls", "/backups").split())


def counts_in_the_container(stack, path="/data/db.sqlite3"):
    return dict(item.rsplit(" ", 1) for item in sidecar(stack, "counts", path).strip().split(", "))


def as_text(counts):
    return {table: str(count) for table, count in counts.items()}


def take_a_backup_now(stack):
    before = set(backups_on_the_volume(stack))
    sidecar(stack, "now")
    [taken] = set(backups_on_the_volume(stack)) - before
    return taken


def logs_of_the_sidecar_once(stack, text, times=1):
    for _ in range(40):
        logs = stack("logs", "backup")
        if logs.count(text) >= times:
            return logs
        time.sleep(0.25)
    pytest.fail(f"The sidecar's log never showed {text!r} {times} times:\n{logs}")


def test_the_sidecar_runs_unprivileged_with_no_network(stack):
    assert stack("exec", "backup", "id", "-u").strip() == "10001"
    assert stack.inspect(".HostConfig.NetworkMode", "backup") == "none"


def test_the_sidecar_waits_for_four_oclock_in_the_deployments_zone(stack):
    logs = logs_of_the_sidecar_once(stack, ANNOUNCEMENT)

    assert f"04:00 {EXAMPLE['TIME_ZONE']}." in logs


def test_a_backup_taken_now_lands_on_the_second_volume_with_every_row(stack):
    # Signing in writes a session row through the app.
    sign_in(stack.port())

    taken = take_a_backup_now(stack)

    mounts = {mount["Destination"]: mount for mount in stack.inspect(".Mounts", "backup")}
    assert (mounts["/backups"]["Type"], mounts["/backups"]["Name"]) == ("volume", f"{stack.project}_backups")
    assert is_backup(taken)
    assert counts_in_the_container(stack, f"/backups/{taken}") == counts_in_the_container(stack)
    assert int(counts_in_the_container(stack)["django_session"]) >= 1


def test_retention_on_the_volume_keeps_the_seven_newest(stack):
    source = take_a_backup_now(stack)
    copies = " && ".join(f"cp /backups/{source} /backups/{name}" for name in PLANTED)
    stack("exec", "backup", "sh", "-c", copies)
    before = backups_on_the_volume(stack)

    taken = take_a_backup_now(stack)

    assert backups_on_the_volume(stack) == sorted([*before, taken])[-KEPT_BACKUPS:]


def test_the_sidecar_stops_promptly_restarts_and_schedules_the_next_night_again(stack):
    kept = backups_on_the_volume(stack)
    started = time.monotonic()
    stack("restart", "backup")

    # Well inside Docker's 10 s grace period, so SIGTERM ended the loop rather than a kill.
    assert time.monotonic() - started < 8
    logs_of_the_sidecar_once(stack, ANNOUNCEMENT, times=2)
    assert stack.inspect(".State.Status", "backup") == "running"
    assert stack.inspect(".HostConfig.RestartPolicy.Name", "backup") == "unless-stopped"
    assert backups_on_the_volume(stack) == kept


def test_a_pulled_backup_restores_into_a_fresh_stack_with_every_row_count(stack, tmp_path):
    session = session_of(sign_in(stack.port())[1])
    taken = take_a_backup_now(stack)
    pulled = tmp_path / "private" / "backups"
    pulled.mkdir(parents=True)
    stack("cp", f"backup:/backups/{taken}", str(pulled))
    expected = row_counts(pulled / taken)
    fresh = local_stack_in(tmp_path)
    try:
        fresh("up", "--detach", "--wait")
        fresh("stop", "ribcage")
        fresh("cp", str(pulled / taken), "backup:/backups/")
        sidecar(fresh, "restore", taken)
        fresh("start", "ribcage")
        wait_until_serving(fresh.port())

        assert counts_in_the_container(fresh) == as_text(expected)
        # The session row came back with the backup, so the voter is still signed in.
        assert SIGNED_IN_AS_THE_VOTER in home_page(fresh.port(), session)[2]
    finally:
        fresh.run("down", "--volumes")
