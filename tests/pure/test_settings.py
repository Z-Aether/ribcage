import re
import runpy
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

import ribcage

SETTINGS_FILE = Path(ribcage.__file__).with_name("settings.py")
EXAMPLE_ENV_FILE = Path(ribcage.__file__).parents[1] / ".env.example"
REQUIRED = [
    "SECRET_KEY",
    "ALLOWED_HOSTS",
    "CSRF_TRUSTED_ORIGINS",
    "DATABASE_PATH",
    "TIME_ZONE",
    "JOIN_CODE",
    "ADMIN_PASSWORD",
    "TMDB_API_KEY",
    "DTDD_API_KEY",
]


def load_settings():
    return runpy.run_path(str(SETTINGS_FILE))


@pytest.mark.parametrize("name", REQUIRED)
def test_a_missing_required_variable_stops_startup_naming_it(monkeypatch, name):
    monkeypatch.delenv(name)

    with pytest.raises(ImproperlyConfigured, match=f"Set the {name} environment variable"):
        load_settings()


@pytest.mark.parametrize("name", REQUIRED)
def test_an_empty_placeholder_counts_as_missing(monkeypatch, name):
    monkeypatch.setenv(name, " ")

    with pytest.raises(ImproperlyConfigured, match=name):
        load_settings()


def test_debug_is_off_unless_switched_on(monkeypatch):
    monkeypatch.delenv("DEBUG", raising=False)
    assert load_settings()["DEBUG"] is False

    monkeypatch.setenv("DEBUG", "True")
    assert load_settings()["DEBUG"] is True


def test_a_malformed_flag_stops_startup_naming_it(monkeypatch):
    monkeypatch.setenv("DEBUG", "yes")

    with pytest.raises(ImproperlyConfigured, match="DEBUG"):
        load_settings()


def test_lists_are_comma_separated(monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", "ribcage.example.org, localhost,")

    assert load_settings()["ALLOWED_HOSTS"] == ["ribcage.example.org", "localhost"]


def test_a_relative_database_path_is_taken_from_the_repo_root(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", "db.sqlite3")
    assert load_settings()["DATABASES"]["default"]["NAME"] == Path(ribcage.__file__).parents[1] / "db.sqlite3"

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "db.sqlite3"))
    assert load_settings()["DATABASES"]["default"]["NAME"] == tmp_path / "db.sqlite3"


def test_simultaneous_sqlite_writers_queue_in_wal_mode(monkeypatch):
    options = load_settings()["DATABASES"]["default"]["OPTIONS"]

    assert options["init_command"] == "PRAGMA journal_mode=WAL;"
    assert options["transaction_mode"] == "IMMEDIATE"
    assert options["timeout"] >= 20


# Defaults as the tickets decided them: #17, #33, #13, #20 and #31.
JUDGEMENT_DEFAULTS = {
    "DIVERSITY_CUT": 4,
    "FLOOR_WEIGHT_MULTIPLIER": 1,
    "BATCH_SIZE": 5,
    "POLL_INTERVAL_SECONDS": 30,
    "TRIGGER_ICON_THRESHOLD": 5,
    "LOGIN_BACKOFF_FAILURES": 5,
    "LOGIN_BACKOFF_WINDOW_MINUTES": 15,
    "LOGIN_BACKOFF_WAIT_MINUTES": 1,
}


@pytest.mark.parametrize(("name", "default"), JUDGEMENT_DEFAULTS.items())
def test_a_judgement_constant_falls_back_to_its_decided_default(monkeypatch, name, default):
    monkeypatch.delenv(name, raising=False)

    assert load_settings()[name] == default


@pytest.mark.parametrize("name", JUDGEMENT_DEFAULTS)
def test_a_judgement_constant_is_overridden_from_the_environment(monkeypatch, name):
    monkeypatch.setenv(name, "7")

    assert load_settings()[name] == 7


@pytest.mark.parametrize("value", ["two", "2.5", "-1"])
def test_a_judgement_constant_that_is_not_a_whole_number_stops_startup_naming_it(monkeypatch, value):
    monkeypatch.setenv("DIVERSITY_CUT", value)

    with pytest.raises(ImproperlyConfigured, match="DIVERSITY_CUT"):
        load_settings()


@pytest.mark.parametrize("name", JUDGEMENT_DEFAULTS)
def test_a_judgement_constant_set_to_zero_stops_startup_naming_it(monkeypatch, name):
    monkeypatch.setenv(name, "0")

    with pytest.raises(ImproperlyConfigured, match=f"Set {name} to a whole number of at least 1"):
        load_settings()


def test_the_example_env_file_names_every_variable_and_nothing_else():
    named = re.findall(r"^#? ?([A-Z_]+)=", EXAMPLE_ENV_FILE.read_text(), re.MULTILINE)

    assert sorted(named) == sorted([*REQUIRED, "DEBUG", *JUDGEMENT_DEFAULTS])


@pytest.mark.parametrize("debug", ["true", "false"])
def test_the_session_cookie_is_secure_http_only_and_same_site_lax_with_debug_on_or_off(monkeypatch, debug):
    monkeypatch.setenv("DEBUG", debug)
    settings = load_settings()

    assert settings["SESSION_COOKIE_SECURE"] is True
    assert settings["SESSION_COOKIE_HTTPONLY"] is True
    assert settings["SESSION_COOKIE_SAMESITE"] == "Lax"
