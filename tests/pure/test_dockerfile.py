import re

import yaml

from tests.image.docker import REPO_ROOT


def test_the_collectstatic_line_sets_every_variable_the_settings_require():
    settings_source = (REPO_ROOT / "ribcage" / "settings.py").read_text(encoding="utf-8")
    required = set(re.findall(r'environment\.required(?:_list)?\("([A-Z_]+)"\)', settings_source))
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    listed = set(re.findall(r"^([A-Z][A-Z_]+)=", example, re.MULTILINE))
    instructions = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8").replace("\\\n", " ").splitlines()
    collectstatic_line = next(line for line in instructions if line.startswith("RUN ") and "collectstatic" in line)
    set_there = set(re.findall(r"\b([A-Z][A-Z_]+)=", collectstatic_line))

    assert required <= listed, f"Add to .env.example: {sorted(required - listed)}"
    assert required <= set_there, f"Add to the Dockerfile's collectstatic line: {sorted(required - set_there)}"


def test_every_volumes_mount_point_is_made_in_the_image_for_the_unprivileged_user():
    # A fresh named volume copies its mount point's owner, so one missing here comes up root-owned and unwritable.
    compose = yaml.safe_load((REPO_ROOT / "compose.yaml").read_text(encoding="utf-8"))
    mount_points = {mount.split(":")[1] for service in compose["services"].values() for mount in service["volumes"]}
    instructions = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    made = re.search(r"install -d -o ribcage -g ribcage (.+)$", instructions, re.MULTILINE)[1].split()

    assert mount_points == set(made)
