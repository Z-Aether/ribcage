import re

import yaml

from ribcage.operations import backup
from tests.image.docker import REPO_ROOT


class Overriding(list):
    """A list an override file tags !override, which replaces the base file's list rather than adding to it."""


class ComposeLoader(yaml.SafeLoader):
    pass


ComposeLoader.add_constructor("!override", lambda loader, node: Overriding(loader.construct_sequence(node)))


def load(name):
    return yaml.load((REPO_ROOT / name).read_text(encoding="utf-8"), Loader=ComposeLoader)


BASE = load("compose.yaml")
LOCAL = load("compose.local.yaml")
APP = BASE["services"]["ribcage"]
BACKUP = BASE["services"]["backup"]
EXAMPLE = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
# Facts of the stack rather than of the host, so they are written here instead of read from its environment.
FIXED = {"DEBUG": "false", "DATABASE_PATH": "/data/db.sqlite3"}
TAG_SCHEME = re.compile(r"\d{8}-\d{4}-[0-9a-f]{7,}")


def every_image():
    return [service["image"] for file in (BASE, LOCAL) for service in file["services"].values() if "image" in service]


def test_the_app_runs_an_image_pinned_to_a_build_tag():
    _, _, tag = APP["image"].rpartition(":")

    assert TAG_SCHEME.fullmatch(tag), APP["image"]


def test_no_image_is_left_to_a_default_or_latest_tag():
    for image in every_image():
        name, _, tag = image.rpartition(":")
        assert name and "/" not in tag and tag != "latest", image


def test_the_app_publishes_only_on_the_hosts_loopback_at_the_proxys_port():
    assert APP["ports"] == ["127.0.0.1:8080:8000"]


def test_no_other_service_publishes_a_port_and_none_joins_the_hosts_network():
    for service in BASE["services"].values():
        assert service is APP or "ports" not in service
        assert service.get("network_mode") != "host"
    assert "networks" not in BASE


def test_every_service_caps_its_json_file_log():
    for service in BASE["services"].values():
        logging = service["logging"]
        assert logging["driver"] == "json-file"
        assert {"max-size", "max-file"} <= set(logging["options"])


def test_the_database_lives_on_a_named_volume_at_data():
    assert "data:/data" in APP["volumes"]
    assert "data" in BASE["volumes"]
    assert FIXED["DATABASE_PATH"].startswith("/data/")


def test_the_app_is_handed_every_setting_in_the_example_env_file():
    named = set(re.findall(r"^#? ?([A-Z][A-Z_]+)=", EXAMPLE, re.MULTILINE))

    assert set(APP["environment"]) == named


def test_every_value_but_the_stacks_own_facts_is_an_empty_placeholder_for_the_hosts_environment():
    for name, value in APP["environment"].items():
        assert value == FIXED.get(name, f"${{{name}:-}}"), name


def test_the_local_override_publishes_the_app_on_loopback_at_the_example_origin_in_place_of_8080():
    assert LOCAL["services"]["ribcage"]["ports"] == ["127.0.0.1:8000:8000"]
    assert isinstance(LOCAL["services"]["ribcage"]["ports"], Overriding)
    assert "http://127.0.0.1:8000" in re.search(r"^CSRF_TRUSTED_ORIGINS=(.*)$", EXAMPLE, re.MULTILINE)[1]


def test_the_local_override_builds_under_its_own_tag_never_the_pinned_one():
    assert LOCAL["services"]["ribcage"]["image"] != APP["image"]


def volume_sources(service):
    return {mount.split(":")[0] for mount in service.get("volumes", [])}


def test_no_service_mounts_anything_from_the_host_only_the_stacks_named_volumes():
    for service in BASE["services"].values():
        assert volume_sources(service) <= set(BASE["volumes"]), service["volumes"]


def test_the_backup_sidecar_runs_the_apps_pinned_image_so_one_repin_moves_both():
    assert BACKUP["image"] == APP["image"]


def test_the_backup_sidecar_runs_its_nightly_loop_instead_of_migrating_and_serving():
    assert BACKUP["command"] == ["python", "-m", "ribcage.operations.backup", "nightly"]
    assert BACKUP["restart"] == "unless-stopped"


def test_the_backup_sidecar_writes_backups_to_a_second_named_volume_at_its_default_path():
    assert f"backups:{backup.BACKUPS.as_posix()}" in BACKUP["volumes"]
    assert set(BASE["volumes"]) == {"data", "backups"}


def test_the_backup_sidecar_reads_the_apps_database_without_a_read_only_mount():
    # A WAL reader writes the -shm file, so a read-only mount would fail it.
    assert "data:/data" in BACKUP["volumes"]
    assert backup.DATABASE.as_posix() == FIXED["DATABASE_PATH"]


def test_the_backup_sidecar_has_no_network_and_is_handed_only_the_time_zone():
    assert BACKUP["network_mode"] == "none"
    assert "networks" not in BACKUP
    assert BACKUP["environment"] == {"TIME_ZONE": "${TIME_ZONE:-}"}


def test_the_local_override_runs_the_sidecar_on_the_apps_local_build():
    assert LOCAL["services"]["backup"]["image"] == LOCAL["services"]["ribcage"]["image"]
    assert "build" not in LOCAL["services"]["backup"]
