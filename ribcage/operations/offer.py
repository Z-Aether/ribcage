# The backup page's offers, for one-time codes made in the ribcage container's terminal (#68, #81).
# Plain Python like the sidecar's module: the command and the page hand it their paths and clock.
import hashlib
import io
import json
import os
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from ribcage.operations.backup import PARTIAL_SUFFIX, backup_name, fails_integrity_check, table_counts, take_backup

DOWNLOAD = "download"
UPLOAD = "upload"
LIFETIME = timedelta(minutes=10)
# The code's record sits beside the offered file, outside the database, so no backup ever holds it (#68).
RECORD = "code.json"
# Several times a marathon's few MB, yet inside gunicorn's 30-second timeout over a 10 Mbit/s upstream (#81).
UPLOAD_CAP_MB = 25
UPLOAD_CAP_BYTES = UPLOAD_CAP_MB * 1024 * 1024
SQLITE_HEADER = b"SQLite format 3\x00"


class Refused(Exception):
    pass


class NoOffer(Refused):
    pass


class Expired(Refused):
    pass


class WrongCode(Refused):
    pass


class WrongPurpose(Refused):
    pass


class Unkept(Exception):
    pass


class TooLarge(Unkept):
    pass


class NotADatabase(Unkept):
    pass


class FailsIntegrityCheck(Unkept):
    pass


@dataclass(frozen=True)
class Offer:
    purpose: str
    file: Path | None


def digest(code):
    # A code of 128 random bits needs no slow hash: there is nothing to brute-force in ten minutes and one guess.
    return hashlib.sha256(code.encode()).hexdigest()


def offer_download(database, directory, now):
    """Take a fresh backup into the directory as its one offer, voiding any earlier one, and return the code and the file."""
    withdraw(directory)
    backup_file = take_backup(database, directory, now)
    return new_code(directory, DOWNLOAD, now, backup_file.name), backup_file


def offer_upload(directory, now):
    """Void any earlier offer and return a code that accepts one upload."""
    withdraw(directory)
    return new_code(directory, UPLOAD, now)


def new_code(directory, purpose, now, file=None):
    code = secrets.token_hex(16)
    write_record(directory, {"purpose": purpose, "digest": digest(code), "expires": (now + LIFETIME).isoformat(), "file": file})
    return code


def withdraw(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # The record goes first, so no post can claim an offer whose file is already gone.
    (directory / RECORD).unlink(missing_ok=True)
    for path in directory.iterdir():
        path.unlink(missing_ok=True)


def write_record(directory, record):
    partial = Path(directory) / f"{RECORD}.partial"
    partial.write_text(json.dumps(record), encoding="utf-8")
    os.replace(partial, Path(directory) / RECORD)


def expires(record):
    return datetime.fromisoformat(record["expires"])


def offered_file(directory, record):
    return Path(directory) / record["file"] if record["file"] else None


def delete_offered_file(directory, record):
    if offered := offered_file(directory, record):
        offered.unlink(missing_ok=True)


def void_if_expired(directory, now):
    try:
        record = json.loads((Path(directory) / RECORD).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    if now >= expires(record):
        void(directory, record)


def void(directory, record):
    (Path(directory) / RECORD).unlink(missing_ok=True)
    delete_offered_file(directory, record)


def claim(directory):
    # Renamed away before it is judged, so of two posts at once only one sees it, and every attempt uses it up (#68).
    record = Path(directory) / RECORD
    claimed = record.with_name(f"claimed-{secrets.token_hex(8)}.json")
    try:
        os.replace(record, claimed)
    except FileNotFoundError:
        raise NoOffer from None
    try:
        return json.loads(claimed.read_text(encoding="utf-8"))
    finally:
        claimed.unlink(missing_ok=True)


def refusal(record, code, now, purpose):
    if now >= expires(record):
        return Expired
    if not secrets.compare_digest(digest(code), record["digest"]):
        return WrongCode
    # A download's code never takes an upload, nor the reverse (#81).
    if record["purpose"] != purpose:
        return WrongPurpose
    return None


def redeem(directory, code, now, purpose):
    """The offer the code is for, used up; the offer is voided and Refused raised if there is none, or the code doesn't fit it."""
    record = claim(directory)
    if refused := refusal(record, code, now, purpose):
        delete_offered_file(directory, record)
        raise refused
    return Offer(purpose, offered_file(directory, record))


def accept_upload(directory, code, chunks, backups, now):
    """Keep an uploaded backup in backups for the sidecar to restore, once it passes its checks and the code redeems."""
    # Named as the sidecar names its own, and only once kept, so a failed or half-written upload never looks like a backup.
    backup_file = Path(backups) / backup_name(now)
    # Its own partial per upload, so two in one second can't delete each other's (#81).
    partial = backup_file.with_name(f"{backup_file.name}.{secrets.token_hex(4)}{PARTIAL_SUFFIX}")
    try:
        write_capped(chunks, partial)
        counts = checked(partial)
        redeem(directory, code, now, UPLOAD)
        os.replace(partial, backup_file)
    finally:
        partial.unlink(missing_ok=True)
    return backup_file, counts


def write_capped(chunks, path):
    written = 0
    with open(path, "wb") as file:
        for chunk in chunks:
            written += len(chunk)
            if written > UPLOAD_CAP_BYTES:
                raise TooLarge
            file.write(chunk)


def checked(path):
    """The row counts of the file, if it is an SQLite database that passes its integrity check."""
    with open(path, "rb") as file:
        # An empty file would pass the integrity check as an empty database.
        if file.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            raise NotADatabase
    # Immutable, so a database uploaded in WAL mode leaves no -wal or -shm file beside it (#81).
    uri = f"{Path(path).resolve().as_uri()}?mode=ro&immutable=1"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            if fails_integrity_check(connection):
                raise FailsIntegrityCheck
            return table_counts(connection)
    except sqlite3.DatabaseError as error:
        raise FailsIntegrityCheck from error


class DeletedOnClose(io.FileIO):
    # Deleted once closed, not once opened: Windows can't delete an open file, and Linux would let it (#68).
    def close(self):
        super().close()
        Path(self.name).unlink(missing_ok=True)


def opened(offer):
    return DeletedOnClose(str(offer.file))
