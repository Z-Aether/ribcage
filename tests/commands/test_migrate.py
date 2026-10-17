import os
import runpy
import sqlite3
import subprocess
import sys
import threading
from contextlib import closing
from pathlib import Path

import pytest
from django.db import transaction
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
