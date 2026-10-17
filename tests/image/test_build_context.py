import shutil

import pytest

from tests.image.docker import REPO_ROOT, build_context_of

pytestmark = pytest.mark.slow

WHAT_THE_IMAGE_NEEDS = {"manage.py", "requirements.txt", "ribcage"}
NEVER_IN_THE_IMAGE = ["private", "tmp", "fixtures", ".git", ".agents", ".claude", ".env", "db.sqlite3"]
PLANTED_OUTSIDE_THE_ALLOWLIST = [
    "private/credentials/tmdb.txt",
    "tmp/scratch.txt",
    "fixtures/dtdd/topics.json",
    ".git/HEAD",
    ".agents/skills/skill.md",
    ".claude/settings.json",
    ".env",
    "db.sqlite3",
    "db.sqlite3-wal",
    "staticfiles/staticfiles.json",
    "docs/design.md",
    "ribcage/.env",
    "ribcage/db.sqlite3",
    "ribcage/__pycache__/settings.cpython-314.pyc",
]
PLANTED_INSIDE_IT = ["manage.py", "requirements.txt", "ribcage/urls.py"]


@pytest.fixture(scope="module")
def build_context(tmp_path_factory):
    return build_context_of(REPO_ROOT, tmp_path_factory.mktemp("build-context"))


def top_level(paths):
    return {path.split("/")[0] for path in paths}


def stray(paths):
    return sorted(
        path
        for path in paths
        if "__pycache__" in path.split("/") or path.rsplit("/", 1)[-1].startswith(".env") or ".sqlite3" in path
    )


def test_the_build_context_holds_only_what_the_image_needs(build_context):
    assert top_level(build_context) == WHAT_THE_IMAGE_NEEDS


@pytest.mark.parametrize("name", NEVER_IN_THE_IMAGE)
def test_nothing_private_scratch_or_agent_owned_is_in_the_build_context(build_context, name):
    assert name not in top_level(build_context)


def test_no_env_file_database_or_bytecode_is_in_the_build_context(build_context):
    assert stray(build_context) == []


def test_the_allowlist_keeps_out_whatever_lies_in_the_forbidden_places(tmp_path):
    # A fresh clone lacks most of these, so the rules are also held against a planted tree.
    planted = tmp_path / "planted"
    for path in PLANTED_OUTSIDE_THE_ALLOWLIST + PLANTED_INSIDE_IT:
        (planted / path).parent.mkdir(parents=True, exist_ok=True)
        (planted / path).write_text("planted")
    shutil.copy(REPO_ROOT / ".dockerignore", planted / ".dockerignore")

    context = build_context_of(planted, tmp_path / "context")

    assert {path for path in context if (planted / path).is_file()} == set(PLANTED_INSIDE_IT)
