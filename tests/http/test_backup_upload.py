import sqlite3
from contextlib import closing

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.html import escape

from ribcage.identity.models import Voter
from ribcage.operations import offer
from ribcage.operations.backup import backup_name, is_backup, row_counts

UPLOAD = "/console/backup/upload/"
FILMS = [("Alien",), ("Heat",), ("Ran",)]


def a_database(path, films=FILMS):
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE films (title TEXT)")
        connection.executemany("INSERT INTO films VALUES (?)", films)
        connection.commit()
    return path


def a_database_failing_its_integrity_check(path):
    # Its index still lists a film its table no longer holds.
    a_database(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE INDEX by_title ON films (title)")
        connection.commit()
        index = connection.execute("SELECT * FROM sqlite_master WHERE name = 'by_title'").fetchone()
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute("DELETE FROM sqlite_master WHERE name = 'by_title'")
        connection.commit()
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("DELETE FROM films WHERE title = 'Heat'")
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute("INSERT INTO sqlite_master VALUES (?, ?, ?, ?, ?)", index)
        connection.commit()
    return path


@pytest.fixture
def pulled(tmp_path):
    """A backup pulled earlier into private/backups/, as the admin's machine holds it."""
    return a_database(tmp_path / "pulled.sqlite3")


@pytest.fixture
def code(clock):
    """An upload's code, made by the container's command a moment ago."""
    return offer.offer_upload(settings.BACKUP_OFFER_DIRECTORY, clock.now)


def upload(client, code, path):
    return client.post(UPLOAD, {"code": code, "backup": SimpleUploadedFile(path.name, path.read_bytes())})


def says(response, text):
    return escape(text) in response.text


def kept_backups():
    return sorted(path.name for path in settings.BACKUP_UPLOAD_DIRECTORY.iterdir())


def code_still_works(client, code, pulled):
    return "Kept <code>backup-" in upload(client, code, pulled).text


def test_the_right_code_keeps_the_backup_beside_the_database_under_a_backups_name(admin, code, pulled, clock):
    response = upload(admin, code, pulled)

    kept = settings.BACKUP_UPLOAD_DIRECTORY / backup_name(clock.now)
    assert kept_backups() == [kept.name]
    assert is_backup(kept.name)
    assert kept.read_bytes() == pulled.read_bytes()
    assert row_counts(kept) == {"films": len(FILMS)}
    assert f"Kept <code>{kept.name}</code>: films 3." in response.text


def test_the_page_names_the_sidecars_restore_from_the_data_volume_and_restores_nothing(admin, code, pulled, clock):
    before = row_counts(pulled)

    response = upload(admin, code, pulled)

    name = backup_name(clock.now)
    assert f"python -m ribcage.operations.backup restore {name} --backups {settings.BACKUP_UPLOAD_DIRECTORY}" in response.text
    assert row_counts(pulled) == before


def test_the_right_code_works_once(admin, code, pulled, clock):
    upload(admin, code, pulled)
    clock.advance(seconds=1)

    response = upload(admin, code, pulled)

    assert "No code is on offer." in response.text
    assert len(kept_backups()) == 1


def test_with_no_offer_nothing_is_kept(admin, pulled):
    response = upload(admin, "0" * 32, pulled)

    assert response.status_code == 200
    assert "No code is on offer." in response.text
    assert kept_backups() == []


def test_a_wrong_code_keeps_nothing_and_voids_the_offer(admin, code, pulled):
    response = upload(admin, "0" * 32, pulled)

    assert "That code is wrong, so it is void and the file was not kept." in response.text
    assert kept_backups() == []
    assert not code_still_works(admin, code, pulled)


def test_a_blank_code_is_no_guess_and_leaves_the_offer(admin, code, pulled):
    response = upload(admin, "", pulled)

    assert kept_backups() == []
    assert "This field is required." in response.text
    assert code_still_works(admin, code, pulled)


def test_a_code_with_no_file_is_no_guess_and_leaves_the_offer(admin, code, pulled):
    response = admin.post(UPLOAD, {"code": code})

    assert kept_backups() == []
    assert "This field is required." in response.text
    assert code_still_works(admin, code, pulled)


def test_the_code_works_until_ten_minutes_have_passed(admin, code, pulled, clock):
    clock.advance(minutes=9, seconds=59)

    assert code_still_works(admin, code, pulled)


def test_an_expired_code_keeps_nothing(admin, code, pulled, clock):
    clock.advance(minutes=10)

    response = upload(admin, code, pulled)

    assert "That code had expired, so it is void and the file was not kept." in response.text
    assert kept_backups() == []


def test_a_download_code_keeps_nothing_and_voids_its_offer(admin, pulled, clock):
    download_code, offered_file = offer.offer_download(pulled, settings.BACKUP_OFFER_DIRECTORY, clock.now)

    response = upload(admin, download_code, pulled)

    assert "That code was made for a download, so it is void and the file was not kept." in response.text
    assert kept_backups() == []
    assert not offered_file.exists()


def test_a_file_that_fails_the_integrity_check_is_deleted_and_the_code_still_works(admin, code, pulled, tmp_path):
    response = upload(admin, code, a_database_failing_its_integrity_check(tmp_path / "broken.sqlite3"))

    assert says(response, "That file failed SQLite's integrity check, so it was not kept.")
    assert kept_backups() == []
    assert code_still_works(admin, code, pulled)


def test_a_file_that_is_not_an_sqlite_database_is_deleted(admin, code, tmp_path):
    not_a_database = tmp_path / "not-a-database.sqlite3"
    not_a_database.write_bytes(b"backup-20261021-120000.sqlite3 is a name, not a database" * 100)

    response = upload(admin, code, not_a_database)

    assert "That file is not an SQLite database, so it was not kept." in response.text
    assert kept_backups() == []


def test_an_empty_file_is_refused_as_empty(admin, code, tmp_path):
    # Else it would pass the integrity check as an empty database.
    empty = tmp_path / "empty.sqlite3"
    empty.write_bytes(b"")

    response = upload(admin, code, empty)

    assert "The submitted file is empty." in response.text
    assert kept_backups() == []


def test_a_database_in_wal_mode_is_kept_with_nothing_beside_it(admin, code, pulled):
    with closing(sqlite3.connect(pulled)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")

    upload(admin, code, pulled)

    assert len(kept_backups()) == 1


@pytest.fixture
def cap_of_a_few_pages(monkeypatch, pulled):
    # The pulled file exactly fills the cap, so one byte more is over it.
    monkeypatch.setattr(offer, "UPLOAD_CAP_BYTES", pulled.stat().st_size)


def test_a_file_over_the_cap_is_never_kept_and_the_code_still_works(admin, code, pulled, tmp_path, cap_of_a_few_pages):
    over_the_cap = tmp_path / "over-the-cap.sqlite3"
    over_the_cap.write_bytes(pulled.read_bytes() + b"\0")

    response = upload(admin, code, over_the_cap)

    assert says(response, f"That file is over {offer.UPLOAD_CAP_MB} MB, far larger than a marathon's backup, so it was not kept.")
    assert kept_backups() == []
    assert code_still_works(admin, code, pulled)


def test_the_upload_handler_drops_a_file_over_the_cap_before_the_view(rf, pulled, cap_of_a_few_pages, tmp_path):
    over_the_cap = tmp_path / "over-the-cap.sqlite3"
    over_the_cap.write_bytes(pulled.read_bytes() + b"\0")
    request = rf.post(UPLOAD, {"code": "x", "backup": SimpleUploadedFile(over_the_cap.name, over_the_cap.read_bytes())})

    assert "backup" not in request.FILES
    assert request.POST["code"] == "x"


def test_a_file_at_the_cap_is_kept(admin, code, pulled, cap_of_a_few_pages):
    upload(admin, code, pulled)

    assert len(kept_backups()) == 1


def signed_in_as_a_voter(client):
    client.force_login(Voter.objects.create_voter("Ada"))
    return client


def anonymous(client):
    return client


@pytest.mark.parametrize("visitor", [signed_in_as_a_voter, anonymous])
def test_without_the_admin_session_the_right_code_gets_the_admin_login_and_keeps_nothing(client, db, code, pulled, clock, visitor):
    response = upload(visitor(client), code, pulled)

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/console/login/?next=")
    assert kept_backups() == []
    assert offer.redeem(settings.BACKUP_OFFER_DIRECTORY, code, clock.now, offer.UPLOAD).file is None


def test_the_upload_takes_posts_alone(admin):
    assert admin.get(UPLOAD).status_code == 405


def test_a_refused_file_leaves_its_working_code_in_the_field(admin, code, tmp_path):
    not_a_database = tmp_path / "notes.txt"
    not_a_database.write_bytes(b"not a database" * 100)

    response = upload(admin, code, not_a_database)

    assert f'name="code" value="{code}"' in response.text


def test_a_refused_code_leaves_the_field_empty(admin, code, pulled):
    response = upload(admin, "0" * 32, pulled)

    assert 'value="' + "0" * 32 not in response.text
    assert code not in response.text


def test_a_wrong_code_with_a_refused_file_is_untried_and_leaves_the_real_code_working(admin, code, pulled, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_bytes(b"not a database" * 100)

    response = upload(admin, "0" * 32, notes)

    assert says(response, "The code wasn't tried, so if it was right it still works.")
    assert "The code still works" not in response.text
    assert code_still_works(admin, code, pulled)


def test_two_uploads_in_one_second_do_not_delete_each_others_partial(code, pulled, clock, monkeypatch):
    # The loser finishes between the winner's redeem and its rename (#81).
    data = pulled.read_bytes()
    real_redeem, losers = offer.redeem, []

    def redeem_then_lose_a_race(*args):
        redeemed = real_redeem(*args)
        if not losers:
            losers.append(True)
            with pytest.raises(offer.NoOffer):
                offer.accept_upload(settings.BACKUP_OFFER_DIRECTORY, code, [data], settings.BACKUP_UPLOAD_DIRECTORY, clock.now)
        return redeemed

    monkeypatch.setattr(offer, "redeem", redeem_then_lose_a_race)

    kept, _ = offer.accept_upload(settings.BACKUP_OFFER_DIRECTORY, code, [data], settings.BACKUP_UPLOAD_DIRECTORY, clock.now)

    assert kept.read_bytes() == data
    assert kept_backups() == [kept.name]
