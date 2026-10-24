"""Every phase move's DoesTheDogDie refresh: the vocabulary, then films oldest first, until the rate limit's floor or 20 s (#32, #104).

It runs after the move commits, in the same request, and each film's write is its own short transaction, so no call to
DoesTheDogDie is made while the write lock is held (#74, #104).
"""

import time
import urllib.error

from django.db import transaction
from django.utils import timezone

from ribcage.suggestions.models import Suggestion
from ribcage.triggers import stored
from ribcage.triggers.client import Client, NoSuchRecord, NotAnswering, dtdd_client, remaining_of
from ribcage.triggers.status import State

# Left for a suggestion's lookup in the same minute (#32 §1, #104).
FLOOR = 3
# Under gunicorn's 30 s worker timeout, with one 5 s call still in flight (#32 §1, #104).
SECONDS = 20


class Spent(Exception):
    """The floor or the time is reached, so the batch ends as a failure does, keeping every snapshot not yet refreshed."""


class Rationed:
    """A transport that makes no call once DoesTheDogDie's remaining count is at the floor or the time is up."""

    def __init__(self, transport, clock):
        self.transport, self.clock = transport, clock
        self.started = clock()
        self.remaining = None

    def __call__(self, path, parameters, headers):
        # Checked before every call, not every film, since a film with no match is several (#104).
        if (self.remaining is not None and self.remaining <= FLOOR) or self.clock() - self.started >= SECONDS:
            raise Spent
        try:
            body, answered = self.transport(path, parameters, headers)
        except urllib.error.HTTPError as error:
            # A 404 spends a call too, so it counts toward the floor; with no header, one off the last count (#104).
            counted = remaining_of(error.headers or {})
            if counted is None and self.remaining is not None:
                counted = self.remaining - 1
            self.remaining = counted
            raise
        self.remaining = remaining_of(answered)
        return body, answered


def after_the_move():
    # The move holds SQLite's write lock, so the refresh waits for its commit, in the same request (#62, 2026-10-21; #104).
    transaction.on_commit(refresh)


def in_line(statuses):
    """The suggestion ids to refresh, in order: not fetched first, as the oldest of all, then by `fetched_at`.

    A film added by hand with no match has nothing to look up, so it is left out; every approval is in (#62, 2026-10-24).
    """
    def oldest_first(pk):
        fetched = statuses[pk].fetched
        return (False, None, pk) if fetched is None else (True, fetched.fetched_at, pk)

    return sorted((pk for pk, status in statuses.items() if status.state is not State.NO_MATCH), key=oldest_first)


def refresh(client=None, clock=time.monotonic):
    """Refresh the vocabulary, then films in line, until the floor, the time, or DoesTheDogDie's first failure.

    A failure ends the whole batch, but a 404 skips only its film: either way a film keeps its old snapshot and is first
    in line next move, never dropped to not fetched. Nothing tells the admin how it went; the Films tab's stale line
    names what is still old (#32 §3, #104).
    """
    client = client or dtdd_client()
    rationed = Client(client.key, Rationed(client.transport, clock))
    try:
        # Replaced whole only once all three lists answer (#23, #104).
        stored.replace_vocabulary(rationed.vocabulary().value)
        suggestions = Suggestion.objects.in_bulk()
        statuses = stored.statuses_of(list(suggestions.values()))
        for pk in in_line(statuses):
            try:
                refresh_one(suggestions[pk], statuses[pk].match, rationed)
            except NoSuchRecord:
                # A record gone from DoesTheDogDie skips only its film, which keeps its snapshot and match (#104, 2026-10-24).
                continue
    except NotAnswering:
        return


def refresh_one(suggestion, match, client):
    # A matched film costs one call; one with no match runs the whole lookup (#32 §1, #101).
    if match is None:
        snapshot = client.lookup(suggestion.tmdb_id, suggestion.title, suggestion.year).value
    else:
        snapshot = client.record(match).value
    stored.store_refresh(suggestion, match, snapshot, timezone.now())
