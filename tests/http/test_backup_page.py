import sqlite3
from contextlib import closing

import pytest
from django.conf import settings

from ribcage.identity.models import Voter
from ribcage.operations import offer
from ribcage.operations.backup import backup_name, row_counts
from tests.http.test_admin_login import sign_in_as_the_admin

PAGE = "/console/backup/"
FILMS = [("Alien",), ("Heat",), ("Ran",)]


@pytest.fixture
def database(tmp_path):
    database = tmp_path / "data" / "db.sqlite3"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE films (title TEXT)")
        connection.executemany("INSERT INTO films VALUES (?)", FILMS)
        connection.commit()
    return database


@pytest.fixture
def offered(database, clock):
    """The code and the file of an offer made by the container's command, a moment ago."""
    return offer.offer_download(database, settings.BACKUP_OFFER_DIRECTORY, clock.now)


def download(client, code):
    return client.post(PAGE, {"code": code})


def is_the_file(response):
    return response.headers.get("Content-Disposition", "").startswith("attachment")


def content_of(response):
    # Read to the end, as a browser would, which closes the response.
    return b"".join(response.streaming_content)


def offer_is_still_there(code, clock):
    return offer.redeem(settings.BACKUP_OFFER_DIRECTORY, code, clock.now, offer.DOWNLOAD).file.exists()


def test_the_right_code_returns_the_offered_backup_as_an_uncached_attachment(admin, offered, tmp_path):
    code, backup_file = offered

    response = download(admin, code)

    assert response.status_code == 200
    assert response.headers["Content-Disposition"] == f'attachment; filename="{backup_file.name}"'
    assert response.headers["Cache-Control"] == "no-store"
    downloaded = tmp_path / "downloaded.sqlite3"
    downloaded.write_bytes(content_of(response))
    assert row_counts(downloaded) == {"films": len(FILMS)}


def test_the_attachment_is_named_for_the_utc_time_the_backup_was_taken(admin, offered, clock):
    code, backup_file = offered

    content_of(download(admin, code))

    assert backup_file.name == backup_name(clock.now)


def test_the_offered_file_is_deleted_once_it_has_been_served(admin, offered):
    code, backup_file = offered

    content_of(download(admin, code))

    assert not backup_file.exists()
    assert list(settings.BACKUP_OFFER_DIRECTORY.iterdir()) == []


def test_the_right_code_works_once(admin, offered):
    code, _ = offered
    content_of(download(admin, code))

    response = download(admin, code)

    assert not is_the_file(response)
    assert "No backup is on offer." in response.text


def test_with_no_offer_any_code_gets_no_file(admin):
    response = download(admin, "0" * 32)

    assert response.status_code == 200
    assert not is_the_file(response)
    assert "No backup is on offer." in response.text


def test_a_wrong_code_gets_no_file_and_voids_the_offer(admin, offered):
    code, backup_file = offered

    response = download(admin, "0" * 32)

    assert not is_the_file(response)
    assert "That code is wrong, so the offer is void." in response.text
    assert not backup_file.exists()
    assert not is_the_file(download(admin, code))


def test_the_code_works_until_ten_minutes_have_passed(admin, offered, clock):
    code, _ = offered
    clock.advance(minutes=9, seconds=59)

    assert is_the_file(download(admin, code))


def test_an_expired_code_gets_no_file_and_deletes_the_offered_file(admin, offered, clock):
    code, backup_file = offered
    clock.advance(minutes=10)

    response = download(admin, code)

    assert not is_the_file(response)
    assert "That code had expired, so the offer is void." in response.text
    assert not backup_file.exists()


def test_opening_the_page_deletes_an_expired_offer(admin, offered, clock):
    _, backup_file = offered
    clock.advance(minutes=10)

    admin.get(PAGE)

    assert list(settings.BACKUP_OFFER_DIRECTORY.iterdir()) == []


def test_opening_the_page_leaves_an_offer_in_its_time(admin, offered, clock):
    code, _ = offered
    clock.advance(minutes=9)

    admin.get(PAGE)

    assert is_the_file(download(admin, code))


def test_the_code_in_an_address_gets_no_file_and_leaves_the_offer(admin, offered, clock):
    # The code travels only in the post's body, so it never reaches the access log (#16, #68).
    code, _ = offered

    response = admin.get(PAGE, {"code": code})

    assert not is_the_file(response)
    assert offer_is_still_there(code, clock)


def test_a_blank_code_is_no_guess_and_leaves_the_offer(admin, offered, clock):
    code, _ = offered

    response = download(admin, "")

    assert not is_the_file(response)
    assert offer_is_still_there(code, clock)


def signed_in_as_a_voter(client):
    client.force_login(Voter.objects.create_voter("Ada"))
    return client


def anonymous(client):
    return client


@pytest.mark.parametrize("visitor", [signed_in_as_a_voter, anonymous])
def test_without_the_admin_session_the_right_code_gets_the_admin_login_and_leaves_the_offer(client, db, offered, clock, visitor):
    code, _ = offered

    response = download(visitor(client), code)

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/console/login/?next=")
    assert offer_is_still_there(code, clock)


def test_the_page_is_a_download_form_and_an_upload_form_under_no_tab(admin):
    page = admin.get(PAGE).text

    assert "console-tabs" not in page
    assert page.count("<form") == 3  # the download's, the upload's, and the header's log out
    assert '<form class="form--short" method="post" action="/console/backup/">' in page
    assert '<form class="form--short" method="post" action="/console/backup/upload/" enctype="multipart/form-data">' in page
    assert page.count('name="code"') == 2
    assert 'type="file" name="backup"' in page


def test_an_upload_code_entered_to_download_gets_no_file_and_voids_it(admin, clock):
    code = offer.offer_upload(settings.BACKUP_OFFER_DIRECTORY, clock.now)

    response = download(admin, code)

    assert not is_the_file(response)
    assert "That code was made for an upload, so the offer is void." in response.text
    with pytest.raises(offer.NoOffer):
        offer.redeem(settings.BACKUP_OFFER_DIRECTORY, code, clock.now, offer.UPLOAD)


def test_no_tab_links_to_the_page(admin):
    for tab in ["/console/phase/", "/console/films/", "/console/pick/", "/console/roster/"]:
        assert PAGE not in admin.get(tab).text


def test_signing_in_as_the_admin_leads_back_to_the_page(client, db):
    response = sign_in_as_the_admin(client, next=PAGE)

    assert response.headers["Location"] == PAGE
