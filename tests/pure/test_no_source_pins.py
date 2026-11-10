"""No test reads the app's own scripts, styles or templates as text: such a test restates the code and fails on every edit."""

import re
from pathlib import Path

TESTS = Path(__file__).parents[1]
ON_DISK = re.compile(r"""ribcage/(static|templates)|["'](static|templates)["']|\bfinders\b|\bSTATIC\b""")
READ = re.compile(r"\bread_text\b|\bread_bytes\b|\bopen\(|\.read\(")
LOADED_TEMPLATE = re.compile(r"\.source\b|\.origin\b")
INSTEAD = "assert on a rendered response, and prove in-browser behaviour in the browser check"
ALLOWED = {
    "vendored.py": "reads the vendored manifest, which names static/vendor/'s files and checksums (#14)",
    "http/test_base_template.py": "holds each vendored file to be served byte for byte with DEBUG off (#46)",
    "http/test_my_warnings.py": "holds the search script to no request call, the privacy wall #108 asks a test for",
}


def reads_front_end_source(text):
    return bool(LOADED_TEMPLATE.search(text) or (ON_DISK.search(text) and READ.search(text)))


def readers():
    files = [path for path in TESTS.rglob("*.py") if path != Path(__file__)]
    return {path.relative_to(TESTS).as_posix() for path in files if reads_front_end_source(path.read_text(encoding="utf-8"))}


def test_no_test_reads_the_apps_scripts_styles_or_templates_as_text():
    pins = sorted(readers() - set(ALLOWED))

    assert not pins, "".join(f"\ntests/{name} reads the app's front-end source: {INSTEAD}." for name in pins)


def test_every_allowed_file_still_reads_what_its_reason_names():
    assert set(ALLOWED) <= readers()
