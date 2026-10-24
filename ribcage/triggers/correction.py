"""Correcting a match: a pasted DoesTheDogDie link previewed, then saved signed, by any voter or the admin (#32 §5, #105).

The preview's GET fetches the record once, outside the write lock, and Use this match's post fetches nothing: the snapshot
travels to it signed, bound to the suggestion it was fetched for, as `films.signed` carries a film (#78, #93).
"""

import re
import urllib.parse
from dataclasses import replace

from django.core import signing
from django.db import transaction
from django.utils import timezone

from ribcage.films.card import MatchCorrection, MatchPreview
from ribcage.suggestions.models import Suggestion
from ribcage.triggers import status, stored
from ribcage.triggers.client import NoSuchRecord, NotAnswering, dtdd_client
from ribcage.triggers.models import TriggerData

SALT = "ribcage.triggers.correction"
HOSTS = {"doesthedogdie.com", "www.doesthedogdie.com"}
ITEM_PAGE = re.compile(r"^/media/(?P<item_id>[0-9]+)(?:/.*)?$")
# The admin's tag, as a voter's is their kept name (#62).
BY_THE_ADMIN = "the admin"

NOT_A_LINK = "That isn't a DoesTheDogDie link. Copy the address of the film's own page there."
NO_SUCH_RECORD = "DoesTheDogDie has no record at that link. Check it's the film's own page."
NOT_ANSWERING = "DoesTheDogDie isn't answering just now. Try again in a minute."


class Refused(ValueError):
    """A pasted link that previews nothing, gently worded; the box keeps it as pasted (#105)."""


class Tampered(ValueError):
    """A signed snapshot whose signature doesn't hold, or one fetched for another film."""


def item_id_in(link):
    """The item id a DoesTheDogDie item page's address names, pasted with or without its scheme, or Refused."""
    pasted = link.strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", pasted, re.I):
        pasted = f"https://{pasted}"
    try:
        parts = urllib.parse.urlsplit(pasted)
        host = parts.hostname
    except ValueError:
        raise Refused(NOT_A_LINK) from None
    found = ITEM_PAGE.match(parts.path)
    if parts.scheme.lower() not in {"http", "https"} or host not in HOSTS or found is None or int(found["item_id"]) == 0:
        raise Refused(NOT_A_LINK)
    return int(found["item_id"])


def offered(at):
    return MatchCorrection(at=at)


def previewed(section, suggestion, link, client=None):
    """The section with its control showing the record the link names, fetched once, or refusing it with the link kept."""
    try:
        snapshot = fetched(item_id_in(link), client or dtdd_client())
    except Refused as refused:
        return replace(section, correction=replace(section.correction, typed=link, refusal=str(refused)))
    record = snapshot.record
    preview = MatchPreview(
        item_id=record.item_id,
        name=record.name,
        year=record.release_year,
        item_type=record.item_type,
        # As the card will list them once it is used, so the count doesn't change across the swap (#62).
        topic_count=named_count(snapshot),
        signed=signed(snapshot, suggestion.pk),
    )
    return replace(section, correction=replace(section.correction, preview=preview))


def fetched(item_id, client):
    # Any item type is accepted: a series added by hand is a "TV Show" there (#19).
    try:
        return client.record(item_id).value
    except NoSuchRecord:
        raise Refused(NO_SUCH_RECORD) from None
    except NotAnswering:
        raise Refused(NOT_ANSWERING) from None


def named_count(snapshot):
    named = {topic.topic_id for topic in stored.stored_vocabulary().topics}
    return len(status.shown_counts(snapshot.counts, named))


def signed(snapshot, suggestion_pk):
    return signing.dumps({"suggestion": suggestion_pk, "snapshot": status.as_data(snapshot)}, salt=SALT, compress=True)


def unsigned(value, suggestion_pk):
    """The snapshot exactly as it was fetched for this suggestion, or Tampered. It never expires, as a signed film doesn't (#93)."""
    try:
        carried = signing.loads(value, salt=SALT)
        snapshot = status.from_data(carried["snapshot"])
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise Tampered from None
    if carried["suggestion"] != suggestion_pk or snapshot.record is None:
        raise Tampered
    return snapshot


def use(suggestion, value, set_by):
    """Use this match: the signed snapshot's record is the match, tagged with its setter, fetched_at now; nothing is fetched.

    A suggestion withdrawn since changes nothing. There is no way back to no match (#105).
    """
    snapshot = unsigned(value, suggestion.pk)
    fetched_now = status.as_text(status.Fetched(snapshot, timezone.now()))
    with transaction.atomic():
        if not Suggestion.objects.filter(pk=suggestion.pk).exists():
            return
        TriggerData.objects.update_or_create(
            suggestion=suggestion, defaults={"match": snapshot.record.item_id, "match_set_by": set_by, "snapshot": fetched_now}
        )
