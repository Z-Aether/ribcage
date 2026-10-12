import os

import pytest

from ribcage import environment


@pytest.fixture(autouse=True)
def _scratch_environment(monkeypatch):
    # load_file writes os.environ directly, so each test gets a copy to write into.
    monkeypatch.setattr(os, "environ", os.environ.copy())


def test_an_env_file_fills_in_variables_the_environment_lacks(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("# a comment\n\nRIBCAGE_TEST_JOIN=a=b$c 'quoted'\n")

    environment.load_file(env_file)

    assert environment.required("RIBCAGE_TEST_JOIN") == "a=b$c 'quoted'"


def test_the_environment_wins_over_an_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("RIBCAGE_TEST_JOIN=from-the-file\n")
    os.environ["RIBCAGE_TEST_JOIN"] = "from-the-environment"

    environment.load_file(env_file)

    assert environment.required("RIBCAGE_TEST_JOIN") == "from-the-environment"


def test_a_missing_env_file_changes_nothing(tmp_path):
    before = dict(os.environ)

    environment.load_file(tmp_path / ".env")

    assert os.environ == before


def test_a_byte_order_mark_does_not_hide_the_first_variable(tmp_path):
    # PowerShell 5 writes one when it saves a .env.
    env_file = tmp_path / ".env"
    env_file.write_text("RIBCAGE_TEST_JOIN=first-line\n", encoding="utf-8-sig")

    environment.load_file(env_file)

    assert environment.required("RIBCAGE_TEST_JOIN") == "first-line"


def test_a_required_value_is_read_without_surrounding_whitespace():
    os.environ["RIBCAGE_TEST_JOIN"] = " local-join-code \t"

    assert environment.required("RIBCAGE_TEST_JOIN") == "local-join-code"
