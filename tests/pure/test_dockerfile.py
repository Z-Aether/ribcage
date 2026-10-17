import re

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
