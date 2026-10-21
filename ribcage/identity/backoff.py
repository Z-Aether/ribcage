"""A timed backoff on repeated failed logins under one key, never a lockout (#16, #31, #71)."""

import math
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from ribcage.identity import display_names
from ribcage.identity.models import LoginFailure

# The admin login's one count, apart from every voter's (#60, #76).
ADMIN_KEY = "admin"


def voter_key(display_name):
    # Every spelling login accepts for a name shares its count, whether or not the name exists (#71).
    return f"voter:{display_names.key(display_name)}"


def wait(key):
    """What is left of the wait under `key`, or None when a login may be tried."""
    now = timezone.now()
    window = timedelta(minutes=settings.LOGIN_BACKOFF_WINDOW_MINUTES)
    length = timedelta(minutes=settings.LOGIN_BACKOFF_WAIT_MINUTES)
    LoginFailure.objects.filter(at__lt=now - length - window).delete()
    latest = LoginFailure.objects.filter(key=key).order_by("-at").values_list("at", flat=True).first()
    if latest is None or now >= latest + length:
        return None
    recent = LoginFailure.objects.filter(key=key, at__gt=latest - window).count()
    return latest + length - now if recent >= settings.LOGIN_BACKOFF_FAILURES else None


def record_failure(key):
    LoginFailure.objects.create(key=key, at=timezone.now())


def clear(key):
    LoginFailure.objects.filter(key=key).delete()


def describe(remaining):
    minutes = math.ceil(remaining / timedelta(minutes=1))
    return "Too many attempts. Try again in a minute." if minutes <= 1 else f"Too many attempts. Try again in {minutes} minutes."
