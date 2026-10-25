"""A suggested film's first DoesTheDogDie lookup, made after its add commits and never inside the write lock (#32, #74, #78, #102)."""

from django.db import transaction
from django.utils import timezone

from ribcage.triggers import stored
from ribcage.triggers.client import NotAnswering, dtdd_client


def after_the_add(suggestion):
    # The add's phase check holds SQLite's write lock, so the lookup waits for the commit, in the same request (#74, #78).
    transaction.on_commit(lambda: look_up(suggestion))


def ensure_vocabulary(client=None):
    """Fetch the vocabulary if none is stored, raising `NotAnswering` when DoesTheDogDie doesn't answer; in RUN nothing is stored (#62, #106, #107)."""
    if not stored.has_vocabulary():
        stored.replace_vocabulary((client or dtdd_client()).vocabulary().value)


def look_up(suggestion, client=None):
    """Store the film's match and snapshot; a failure leaves it not fetched, and the suggestion stands (#32 §2).

    A film added by hand looks nothing up, and a missing vocabulary is fetched first, as on a fresh database (#62).
    """
    if suggestion.tmdb_id is None:
        return
    client = client or dtdd_client()
    try:
        ensure_vocabulary(client)
        snapshot = client.lookup(suggestion.tmdb_id, suggestion.title, suggestion.year).value
    except NotAnswering:
        return
    stored.store_lookup(suggestion, snapshot, timezone.now())
