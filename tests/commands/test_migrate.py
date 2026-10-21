import os
import runpy
import sqlite3
import subprocess
import sys
import threading
from contextlib import closing
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import connection, transaction
from django.db.utils import ConnectionHandler

import ribcage

REPO_ROOT = Path(ribcage.__file__).parents[1]


def test_a_fresh_database_comes_up_in_wal_mode(tmp_path):
    database = tmp_path / "fresh.sqlite3"
    environ = {**os.environ, "DJANGO_SETTINGS_MODULE": "ribcage.settings", "DATABASE_PATH": str(database)}

    migrate = subprocess.run(
        [sys.executable, "manage.py", "migrate", "--verbosity", "0"],
        cwd=REPO_ROOT,
        env=environ,
        capture_output=True,
        text=True,
    )

    assert migrate.returncode == 0, migrate.stderr
    # WAL is recorded in the file, so a plain connection that sets nothing still reads it.
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


@pytest.fixture
def private_connections(django_db_blocker):
    # The test opens its own connections to a temp file, so the suite's database block is lifted for it.
    with django_db_blocker.unblock():
        yield


def test_a_write_after_a_read_waits_for_a_concurrent_writer_instead_of_failing(tmp_path, monkeypatch, private_connections):
    options = runpy.run_path(str(REPO_ROOT / "ribcage" / "settings.py"))["DATABASES"]["default"]["OPTIONS"]
    databases = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": tmp_path / "race.sqlite3", "OPTIONS": options}}
    reader = ConnectionHandler(databases)["default"]
    rival_connections = ConnectionHandler(databases)
    monkeypatch.setattr(transaction, "get_connection", lambda using=None: reader)
    with reader.cursor() as cursor:
        cursor.execute("CREATE TABLE tally (n INTEGER)")
    outcome = []

    def rival_write():
        with rival_connections["default"].cursor() as cursor:
            cursor.execute("INSERT INTO tally VALUES (2)")
        outcome.append("committed")

    rival = threading.Thread(target=rival_write)
    with transaction.atomic():
        with reader.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM tally")
            rival.start()
            rival.join(0.3)
            cursor.execute("INSERT INTO tally VALUES (1)")
    rival.join(10)

    assert outcome == ["committed"]


def test_migrating_a_database_that_holds_voters_gives_each_the_key_of_its_name(tmp_path):
    database = tmp_path / "old.sqlite3"
    environ = {**os.environ, "DJANGO_SETTINGS_MODULE": "ribcage.settings", "DATABASE_PATH": str(database)}

    def migrate(*target):
        run = subprocess.run(
            [sys.executable, "manage.py", "migrate", "--verbosity", "0", *target],
            cwd=REPO_ROOT,
            env=environ,
            capture_output=True,
            text=True,
        )
        assert run.returncode == 0, run.stderr

    migrate("identity", "0001")
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.executemany(
            "INSERT INTO identity_voter (password, display_name) VALUES ('', ?)", [("\u00c9va",), ("Sam",)]
        )
    migrate()

    with closing(sqlite3.connect(database)) as connection:
        keys = connection.execute("SELECT display_name, display_name_key FROM identity_voter ORDER BY id").fetchall()
    assert keys == [("\u00c9va", "\u00e9va"), ("Sam", "sam")]


def test_migrating_drops_the_removed_hello_apps_table(transactional_db):
    # The deployed database still holds M1's hello table, and the hello app is gone (#47, #70).
    call_command("migrate", "identity", "0002", verbosity=0)
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE hello_message (id INTEGER PRIMARY KEY, text VARCHAR(200))")

    call_command("migrate", verbosity=0)

    assert "hello_message" not in connection.introspection.table_names()
