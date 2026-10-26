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
from django.db.migrations.executor import MigrationExecutor
from django.db.utils import ConnectionHandler

import ribcage

REPO_ROOT = Path(ribcage.__file__).parents[1]


def migrate(database, *target):
    environ = {**os.environ, "DJANGO_SETTINGS_MODULE": "ribcage.settings", "DATABASE_PATH": str(database)}
    run = subprocess.run(
        [sys.executable, "manage.py", "migrate", "--verbosity", "0", *target],
        cwd=REPO_ROOT,
        env=environ,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr


def test_a_fresh_database_comes_up_in_wal_mode(tmp_path):
    database = tmp_path / "fresh.sqlite3"

    migrate(database)

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


def test_migrating_a_database_that_holds_voters_gives_each_the_key_of_its_name_and_forces_no_change(tmp_path):
    database = tmp_path / "old.sqlite3"

    migrate(database, "identity", "0001")
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.executemany(
            "INSERT INTO identity_voter (password, display_name) VALUES ('', ?)", [("\u00c9va",), ("Sam",)]
        )
    migrate(database)

    with closing(sqlite3.connect(database)) as connection:
        voters = connection.execute("SELECT display_name, display_name_key, must_change_password FROM identity_voter ORDER BY id").fetchall()
    # Only an admin reset forces a change, so no voter already registered is sent to the form (#80).
    assert voters == [("\u00c9va", "\u00e9va", 0), ("Sam", "sam", 0)]


def test_migrating_drops_the_removed_hello_apps_table(transactional_db):
    # The deployed database still holds M1's hello table, and the hello app is gone (#47, #70).
    call_command("migrate", "identity", "0002", verbosity=0)
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE hello_message (id INTEGER PRIMARY KEY, text VARCHAR(200))")

    call_command("migrate", verbosity=0)

    assert "hello_message" not in connection.introspection.table_names()


def test_migrating_moves_a_veto_reason_into_the_voters_note_creating_it_or_appending_to_it(transactional_db):
    # A reason became the voter's note on the film, so none is lost when the field goes (#128).
    executor = MigrationExecutor(connection)
    executor.migrate([("ballot", "0001_ballot_records_and_done_markers")])
    # The voters as they are now, the ballot's records as they were.
    old = executor.loader.project_state([("ballot", "0001_ballot_records_and_done_markers"), *executor.loader.graph.leaf_nodes("identity")]).apps
    Voter, Suggestion, Note, Record = (old.get_model(app, name) for app, name in (("identity", "Voter"), ("suggestions", "Suggestion"), ("suggestions", "Note"), ("ballot", "BallotRecord")))
    voters = [Voter.objects.create(display_name=name, display_name_key=name.lower(), password="") for name in ("Ada", "Zoe", "Sam")]
    film = Suggestion.objects.create(title="Terrifier", suggester_name="Ada", runtime=100)
    Note.objects.create(suggestion=film, author=voters[1], text="Very gory.")
    Record.objects.create(voter=voters[0], suggestion=film, vetoed=True, veto_reason="Too much.")
    Record.objects.create(voter=voters[1], suggestion=film, vetoed=True, veto_reason="Not again.")
    Record.objects.create(voter=voters[2], suggestion=film, vetoed=True)

    try:
        call_command("migrate", verbosity=0)
        notes = dict(Note.objects.values_list("author__display_name", "text"))
        assert notes == {"Ada": "Too much.", "Zoe": "Very gory.\n\nNot again."}
        assert "veto_reason" not in {column.name for column in connection.introspection.get_table_description(connection.cursor(), "ballot_ballotrecord")}
    finally:
        call_command("migrate", verbosity=0)
