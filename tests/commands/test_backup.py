import os
import re
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command

import ribcage
from ribcage.operations import backup, offer
from ribcage.operations.backup import KEPT_BACKUPS, BackupFailed, restore, row_counts, take_backup

REPO_ROOT = Path(ribcage.__file__).parents[1]
TAKEN_AT = datetime(2026, 10, 18, 3, tzinfo=UTC)
WRITTEN_AFTER_THE_SEED = 50


def run_in_a_child(*arguments, **environment):
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=REPO_ROOT,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "ribcage.settings", **environment},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def seed(database):
    seeding = run_in_a_child("manage.py", "seed", DATABASE_PATH=str(database), DEBUG="true")
    assert seeding.returncode == 0, seeding.stderr


@pytest.fixture(scope="module")
def seeded_template(tmp_path_factory):
    database = tmp_path_factory.mktemp("seeded") / "db.sqlite3"
    seed(database)
    return database


@pytest.fixture
def live_database(seeded_template, tmp_path):
    # The seed's own connection checkpointed on closing; this one keeps its writes in the WAL until the test ends.
    database = tmp_path / "data" / "db.sqlite3"
    database.parent.mkdir()
    shutil.copy(seeded_template, database)
    with closing(sqlite3.connect(database)) as writer:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE written_after_the_seed (n INTEGER)")
        rows = [(n,) for n in range(WRITTEN_AFTER_THE_SEED)]
        writer.executemany("INSERT INTO written_after_the_seed VALUES (?)", rows)
        writer.execute("DELETE FROM identity_voter WHERE display_name = 'Ada'")
        writer.commit()
        yield database


@pytest.fixture
def backups(tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    return directory


def counts_in_the_main_file_alone(database, scratch):
    # What a file copy of the live database would hold.
    copy = scratch / "main-file-alone.sqlite3"
    shutil.copy(database, copy)
    return row_counts(copy)


def test_the_live_database_holds_uncheckpointed_writes_in_its_wal(live_database, tmp_path):
    live = row_counts(live_database)

    assert Path(f"{live_database}-wal").stat().st_size > 0
    assert live["written_after_the_seed"] == WRITTEN_AFTER_THE_SEED
    assert live["identity_voter"] == 5
    assert counts_in_the_main_file_alone(live_database, tmp_path) != live


def test_the_sidecars_command_takes_a_backup_of_every_table_and_row_including_the_wal(live_database, backups):
    taken = run_in_a_child(
        "-m", "ribcage.operations.backup", "now", "--database", str(live_database), "--backups", str(backups)
    )

    assert taken.returncode == 0, taken.stderr
    [backup_file] = backups.iterdir()
    assert row_counts(backup_file) == row_counts(live_database)
    assert f"Took {backup_file.name}" in taken.stdout


def test_a_backup_is_one_self_contained_file_that_passes_the_integrity_check(live_database, backups):
    backup_file = take_backup(live_database, backups, TAKEN_AT)

    assert sorted(path.name for path in backups.iterdir()) == [backup_file.name]
    with closing(sqlite3.connect(backup_file)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]


def test_a_backup_that_fails_its_integrity_check_never_counts(live_database, backups, monkeypatch):
    monkeypatch.setattr(backup, "fails_integrity_check", lambda connection: True)

    with pytest.raises(BackupFailed, match="integrity check"):
        take_backup(live_database, backups, TAKEN_AT)

    assert list(backups.iterdir()) == []


def test_a_half_written_backup_left_by_a_crash_is_cleared_and_never_counted(live_database, backups):
    leftover = backups / (backup.backup_name(TAKEN_AT - timedelta(days=1)) + backup.PARTIAL_SUFFIX)
    leftover.write_bytes(b"cut off mid-write")

    backup_file = take_backup(live_database, backups, TAKEN_AT)

    assert sorted(path.name for path in backups.iterdir()) == [backup_file.name]


def test_with_no_database_yet_it_fails_without_creating_one_or_deleting_any_backup(
    live_database, backups, tmp_path
):
    for day in range(KEPT_BACKUPS + 1):
        take_backup(live_database, backups, TAKEN_AT - timedelta(days=day))
    missing = tmp_path / "missing" / "db.sqlite3"
    missing.parent.mkdir()
    before = sorted(backups.iterdir())

    assert backup.take_backup_and_prune(missing, backups) is False

    assert not missing.exists()
    assert sorted(backups.iterdir()) == before


def test_each_backup_keeps_only_the_seven_newest(live_database, backups):
    taken = [take_backup(live_database, backups, TAKEN_AT - timedelta(days=day)) for day in range(9, 0, -1)]

    assert backup.take_backup_and_prune(live_database, backups) is True

    remaining = sorted(path.name for path in backups.iterdir())
    assert len(remaining) == KEPT_BACKUPS
    assert remaining[:-1] == [path.name for path in taken[-(KEPT_BACKUPS - 1) :]]


def test_a_backup_restores_over_a_fresh_database_with_every_row_count(
    live_database, backups, seeded_template, tmp_path
):
    backup_file = take_backup(live_database, backups, TAKEN_AT)
    fresh = tmp_path / "fresh" / "db.sqlite3"
    fresh.parent.mkdir()
    shutil.copy(seeded_template, fresh)

    restored = restore(backup_file, fresh)

    assert restored == row_counts(backup_file) == row_counts(live_database)
    with closing(sqlite3.connect(fresh)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_counts_prints_every_tables_row_count(live_database):
    counted = run_in_a_child("-m", "ribcage.operations.backup", "counts", str(live_database))

    assert counted.returncode == 0, counted.stderr
    assert f"written_after_the_seed {WRITTEN_AFTER_THE_SEED}" in counted.stdout
    assert "identity_voter 5" in counted.stdout


def test_restore_refuses_a_broken_backup_and_leaves_the_database_alone(live_database, backups):
    broken = backups / backup.backup_name(TAKEN_AT)
    broken.write_bytes(b"a file of a plausible name that is not a database" * 100)
    before = row_counts(live_database)

    restoring = run_in_a_child(
        "-m", "ribcage.operations.backup", "restore", broken.name,
        "--backups", str(backups), "--database", str(live_database),
    )

    assert restoring.returncode != 0
    assert row_counts(live_database) == before


def offered_files(directory):
    return [path for path in directory.iterdir() if backup.is_backup(path.name)]


def test_the_backup_code_command_offers_a_backup_that_passes_the_integrity_check_with_the_databases_counts(live_database):
    offering = run_in_a_child("manage.py", "backupcode", "download", DATABASE_PATH=str(live_database))

    assert offering.returncode == 0, offering.stderr
    [backup_file] = offered_files(live_database.parent / "backup-offer")
    with closing(sqlite3.connect(backup_file)) as connection:
        assert not backup.fails_integrity_check(connection)
    assert row_counts(backup_file) == row_counts(live_database)
    assert f"Offered {backup_file.name}: " in offering.stdout
    assert "/console/backup/" in offering.stdout


def test_the_code_the_command_prints_redeems_its_offer(live_database):
    offering = run_in_a_child("manage.py", "backupcode", "download", DATABASE_PATH=str(live_database))
    [code] = re.findall(r"^Code: ([0-9a-f]{32})$", offering.stdout, re.M)

    redeemed = offer.redeem(live_database.parent / "backup-offer", code, datetime.now(UTC))

    assert redeemed.purpose == offer.DOWNLOAD
    assert row_counts(redeemed.file) == row_counts(live_database)


def test_a_new_offer_voids_the_last_and_deletes_its_file(live_database, tmp_path):
    directory = tmp_path / "backup-offer"
    first_code, first_file = offer.offer_download(live_database, directory, TAKEN_AT)

    _, second_file = offer.offer_download(live_database, directory, TAKEN_AT + timedelta(minutes=1))

    assert offered_files(directory) == [second_file]
    assert not first_file.exists()
    with pytest.raises(offer.WrongCode):
        offer.redeem(directory, first_code, TAKEN_AT + timedelta(minutes=2))


def test_with_no_database_the_command_fails_and_offers_nothing(tmp_path):
    missing = tmp_path / "data" / "db.sqlite3"

    offering = run_in_a_child("manage.py", "backupcode", "download", DATABASE_PATH=str(missing))

    assert offering.returncode != 0
    assert "No backup offered" in offering.stderr
    assert not missing.exists()
    assert list((tmp_path / "data" / "backup-offer").iterdir()) == []


def test_the_backup_code_command_refuses_to_run_as_root_and_touches_nothing(tmp_path, monkeypatch, settings):
    settings.BACKUP_OFFER_DIRECTORY = tmp_path / "backup-offer"
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)

    with pytest.raises(CommandError, match="not root"):
        call_command("backupcode", "download")

    assert not (tmp_path / "backup-offer").exists()
