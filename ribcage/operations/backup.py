# Plain Python that never loads Django's settings, so the backup sidecar is handed none of the app's secrets (#53).
import argparse
import os
import re
import signal
import sqlite3
import sys
import time
from contextlib import closing
from datetime import UTC, datetime, time as clock_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ribcage import environment

# The sidecar's mounts in compose.yaml.
DATABASE = Path("/data/db.sqlite3")
BACKUPS = Path("/backups")
# One bad night must not displace the last good backup, and teardown bounds the rest (#30).
KEPT_BACKUPS = 7
# A quiet hour in the deployment's TIME_ZONE; no ticket asks for it to be configurable (#36).
BACKUP_HOUR = 4
# Named in UTC, so sorting by name is sorting by age, across DST changes too.
BACKUP_NAME = "backup-%Y%m%d-%H%M%S.sqlite3"
BACKUP_PATTERN = re.compile(r"backup-\d{8}-\d{6}\.sqlite3")
# A file is written under this suffix and renamed once checked, so a half-written one never counts.
PARTIAL_SUFFIX = ".partial"
LONGEST_SLEEP_SECONDS = 300
BUSY_TIMEOUT_SECONDS = 20


class BackupFailed(Exception):
    pass


def backup_name(taken_at):
    return taken_at.astimezone(UTC).strftime(BACKUP_NAME)


def is_backup(name):
    return BACKUP_PATTERN.fullmatch(name) is not None


def backups_beyond_retention(names):
    return sorted(filter(is_backup, names))[:-KEPT_BACKUPS]


def next_backup_time(now, zone):
    local_now = now.astimezone(zone)
    # Worked out from the clock alone, so a restart neither skips nor repeats a night.
    for day in (local_now.date(), local_now.date() + timedelta(days=1)):
        due = datetime.combine(day, clock_time(BACKUP_HOUR), zone)
        if due > local_now:
            return due


def open_existing(database, mode="rw"):
    # Never creates the file: before the app's first start there is nothing to back up.
    uri = f"{Path(database).resolve().as_uri()}?mode={mode}"
    try:
        return sqlite3.connect(uri, uri=True, timeout=BUSY_TIMEOUT_SECONDS)
    except sqlite3.OperationalError as error:
        raise BackupFailed(f"Can't open {database}: {error}.") from error


def fails_integrity_check(connection):
    return [row[0] for row in connection.execute("PRAGMA integrity_check")] != ["ok"]


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def row_counts(database):
    with closing(open_existing(database, mode="ro")) as connection:
        tables = [name for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {quoted(table)}").fetchone()[0]
            for table in sorted(tables)
        }


def take_backup(database, backups, taken_at):
    backup_file = Path(backups) / backup_name(taken_at)
    partial = backup_file.with_name(backup_file.name + PARTIAL_SUFFIX)
    for leftover in Path(backups).glob(f"*{PARTIAL_SUFFIX}*"):
        leftover.unlink()
    try:
        # SQLite's online backup reads the WAL too; a file copy of a live WAL database is a broken backup (#25).
        with closing(open_existing(database)) as source, closing(sqlite3.connect(partial)) as target:
            source.backup(target)
            # A rollback journal makes the backup one self-contained file; the app turns WAL back on (#52).
            target.execute("PRAGMA journal_mode=DELETE")
            # Checked before it counts, so a broken backup never pushes a good one out of the seven.
            if fails_integrity_check(target):
                raise BackupFailed(f"The backup of {database} failed SQLite's integrity check.")
        os.replace(partial, backup_file)
    finally:
        partial.unlink(missing_ok=True)
    return backup_file


def prune(backups):
    deleted = backups_beyond_retention(path.name for path in Path(backups).iterdir())
    for name in deleted:
        (Path(backups) / name).unlink()
    return deleted


def take_backup_and_prune(database, backups):
    try:
        backup_file = take_backup(database, backups, datetime.now(UTC))
    except (BackupFailed, sqlite3.Error) as error:
        say(f"Backup failed, older backups kept: {error}")
        return False
    say(f"Took {backup_file.name}: {describe(row_counts(backup_file))}.")
    for name in prune(backups):
        say(f"Deleted {name}, keeping the {KEPT_BACKUPS} newest.")
    return True


def restore(backup_file, database):
    with closing(open_existing(backup_file, mode="ro")) as source:
        if fails_integrity_check(source):
            raise BackupFailed(f"{backup_file} failed SQLite's integrity check, so it was not restored.")
        # Through SQLite, never a file copy, so a WAL left beside the database can't be replayed onto it.
        with closing(sqlite3.connect(database, timeout=BUSY_TIMEOUT_SECONDS)) as target:
            source.backup(target)
            target.execute("PRAGMA journal_mode=WAL")
    return row_counts(database)


def run_nightly(database, backups, zone):
    while True:
        due = next_backup_time(datetime.now(UTC), zone)
        say(f"Next backup at {due:%Y-%m-%d %H:%M} {zone.key}.")
        # Short sleeps re-read the clock, so a host suspend or clock change can't push the backup back.
        while (remaining := (due - datetime.now(UTC)).total_seconds()) > 0:
            time.sleep(min(remaining, LONGEST_SLEEP_SECONDS))
        take_backup_and_prune(database, backups)


def describe(counts):
    return ", ".join(f"{table} {count}" for table, count in counts.items())


def say(message):
    print(message, flush=True)


def stop_on_sigterm():
    # As PID 1 the default SIGTERM is ignored, so docker stop would wait out its grace period.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))


def parser():
    commands = argparse.ArgumentParser(
        prog="python -m ribcage.operations.backup",
        description="The backup sidecar's backups, and the restore drill's tools (#53).",
    )
    subcommands = commands.add_subparsers(dest="command", required=True)
    # Defaults name the sidecar's paths, so no command needs a leading slash, which Git Bash rewrites.
    for name, help in [
        ("nightly", f"Take a backup at {BACKUP_HOUR:02}:00 in TIME_ZONE every night; the sidecar's command."),
        ("now", f"Take a backup now, then delete all but the newest {KEPT_BACKUPS}."),
        ("restore", "Restore the named backup over the database. Stop the app first."),
    ]:
        command = subcommands.add_parser(name, help=help)
        if name == "restore":
            command.add_argument("backup", help="A backup's file name, looked up in --backups.")
        command.add_argument("--database", type=Path, default=DATABASE)
        command.add_argument("--backups", type=Path, default=BACKUPS)
    counts = subcommands.add_parser("counts", help="Check a database or backup opens, and print its row counts.")
    counts.add_argument("database", type=Path, nargs="?", default=DATABASE)
    return commands


def main(arguments=None):
    options = parser().parse_args(arguments)
    if options.command == "nightly":
        stop_on_sigterm()
        run_nightly(options.database, options.backups, ZoneInfo(environment.required("TIME_ZONE")))
    elif options.command == "now":
        return 0 if take_backup_and_prune(options.database, options.backups) else 1
    elif options.command == "counts":
        say(describe(row_counts(options.database)))
    elif options.command == "restore":
        restored = restore(options.backups / options.backup, options.database)
        say(f"Restored {options.backup}: {describe(restored)}.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (BackupFailed, sqlite3.DatabaseError) as error:
        sys.exit(str(error))
