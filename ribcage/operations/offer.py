# The backup page's offers, for one-time codes made in the ribcage container's terminal (#68).
# Plain Python like the sidecar's module: the command and the page hand it their paths and clock.
import hashlib
import io
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from ribcage.operations.backup import take_backup

DOWNLOAD = "download"
LIFETIME = timedelta(minutes=10)
# The code's record sits beside the offered file, outside the database, so no backup ever holds it (#68).
RECORD = "code.json"


class Refused(Exception):
    pass


class NoOffer(Refused):
    pass


class Expired(Refused):
    pass


class WrongCode(Refused):
    pass


@dataclass(frozen=True)
class Offer:
    purpose: str
    file: Path


def digest(code):
    # A code of 128 random bits needs no slow hash: there is nothing to brute-force in ten minutes and one guess.
    return hashlib.sha256(code.encode()).hexdigest()


def offer_download(database, directory, now):
    """Take a fresh backup into the directory as its one offer, voiding any earlier one, and return the code and the file."""
    withdraw(directory)
    backup_file = take_backup(database, directory, now)
    code = secrets.token_hex(16)
    write_record(directory, {"purpose": DOWNLOAD, "digest": digest(code), "expires": (now + LIFETIME).isoformat(), "file": backup_file.name})
    return code, backup_file


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


def void_if_expired(directory, now):
    try:
        record = json.loads((Path(directory) / RECORD).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    if now >= expires(record):
        void(directory, record)


def void(directory, record):
    (Path(directory) / RECORD).unlink(missing_ok=True)
    (Path(directory) / record["file"]).unlink(missing_ok=True)


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


def redeem(directory, code, now):
    """The offer the code is for, used up; the offer is voided and Refused raised if there is none, it expired or the code is wrong."""
    record = claim(directory)
    offer = Offer(record["purpose"], Path(directory) / record["file"])
    if now >= expires(record):
        offer.file.unlink(missing_ok=True)
        raise Expired
    if not secrets.compare_digest(digest(code), record["digest"]):
        offer.file.unlink(missing_ok=True)
        raise WrongCode
    return offer


class DeletedOnClose(io.FileIO):
    # Deleted once closed, not once opened: Windows can't delete an open file, and Linux would let it (#68).
    def close(self):
        super().close()
        Path(self.name).unlink(missing_ok=True)


def opened(offer):
    return DeletedOnClose(str(offer.file))
