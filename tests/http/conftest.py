from datetime import timedelta

import pytest
from django.utils import timezone

from ribcage.films import client
from ribcage.identity.models import Voter
from tests.http.signing_in import CODE, PASSWORD, sign_in_as_the_admin


@pytest.fixture(autouse=True)
def _static_files_collected(collected_static_files):
    # Every page here renders base.html's static tags; the pure suite never pays for collectstatic (#46).
    pass


@pytest.fixture(autouse=True)
def _fast_hashing(fast_hashing):
    pass


@pytest.fixture(autouse=True)
def _known_join_code(settings):
    settings.JOIN_CODE = CODE


@pytest.fixture(autouse=True)
def _backup_offer_directory(settings, tmp_path):
    # Every test's backup offer is its own, never one beside the developer's database (#68).
    settings.BACKUP_OFFER_DIRECTORY = tmp_path / "backup-offer"
    # And its uploads land in its own stand-in for the data volume (#81).
    settings.BACKUP_UPLOAD_DIRECTORY = tmp_path / "data"
    settings.BACKUP_UPLOAD_DIRECTORY.mkdir()


@pytest.fixture(autouse=True)
def _tmdb_never_reached(monkeypatch):
    # No test goes online: TMDB is answered by a fake transport, or not at all (#25, #92).
    def offline(path, parameters, headers):
        raise ConnectionError(f"A test asked TMDB for {path}; give it a fake transport.")

    monkeypatch.setattr(client, "over_the_network", offline)


class Clock:
    def __init__(self):
        self.now = timezone.now()

    def advance(self, **delta):
        self.now += timedelta(**delta)


@pytest.fixture
def clock(monkeypatch):
    # The login backoffs read the time through timezone.now (#71, #76).
    clock = Clock()
    monkeypatch.setattr(timezone, "now", lambda: clock.now)
    return clock


@pytest.fixture
def admin(client, db):
    sign_in_as_the_admin(client)
    return client


@pytest.fixture
def voters(db):
    # The Roster tab's voters, the second lower-case so its order is case-blind (#79).
    return {name: Voter.objects.create_voter(name, PASSWORD) for name in ["Hanna", "ada", "Dani"]}
