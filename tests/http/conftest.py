from datetime import timedelta

import pytest
from django.utils import timezone

from tests.http.test_admin_login import sign_in_as_the_admin


@pytest.fixture(autouse=True)
def _static_files_collected(collected_static_files):
    # Every page here renders base.html's static tags; the pure suite never pays for collectstatic (#46).
    pass


@pytest.fixture(autouse=True)
def _backup_offer_directory(settings, tmp_path):
    # Every test's backup offer is its own, never one beside the developer's database (#68).
    settings.BACKUP_OFFER_DIRECTORY = tmp_path / "backup-offer"


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
