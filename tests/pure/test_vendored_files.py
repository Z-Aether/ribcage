import hashlib

from tests.vendored import MANIFEST, VENDOR, recorded_files


def test_every_vendored_file_matches_its_recorded_checksum():
    for path, sha256 in recorded_files().items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha256, path


def test_every_file_in_the_vendor_directory_is_recorded():
    present = {path for path in VENDOR.rglob("*") if path.is_file() and path != MANIFEST}

    assert present == set(recorded_files())
