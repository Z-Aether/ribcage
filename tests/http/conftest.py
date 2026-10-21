from datetime import timedelta

import pytest
from django.utils import timezone


@pytest.fixture(autouse=True)
def _static_files_collected(collected_static_files):
    # Every page here renders base.html's static tags; the pure suite never pays for collectstatic (#46).
    pass


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
