"""The DoesTheDogDie client, the app's second outbound call and its one trigger source, shaped as TMDB's is (#5, #19, #32, #101)."""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from ribcage.triggers import dtdd, vocabulary

DTDD_API = "https://www.doesthedogdie.com/api/v3"
# A slow DoesTheDogDie reads as one not answering, inside gunicorn's timeout (#32, #62).
TIMEOUT_SECONDS = 5
REMAINING_HEADER = "x-ratelimit-remaining-minute"

# What the seeded instance answers DoesTheDogDie from instead of the network, with DEBUG on alone (#50, #102).
stand_in = None


class NotAnswering(Exception):
    """DoesTheDogDie didn't answer: a timeout, a refused key, a 5xx, a 429 or a malformed answer alike (#32)."""


class NoSuchRecord(NotAnswering):
    """DoesTheDogDie answered 404: a pasted link names no record. Every caller but `refresh.refresh`, which skips only its film, reads it as not answering (#104, #105)."""


@dataclass(frozen=True)
class Answer:
    value: Any
    # DoesTheDogDie's live count after the last call, so the refresh stops on it; None is no limit in sight (#32 §1).
    remaining: int | None


def over_the_network(path, parameters, headers):
    query = f"?{urllib.parse.urlencode(parameters)}" if parameters else ""
    request = urllib.request.Request(f"{DTDD_API}{path}{query}", headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read()), dict(response.headers.items())


def remaining_of(headers):
    value = {name.lower(): value for name, value in headers.items()}.get(REMAINING_HEADER)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class Client:
    def __init__(self, key, transport=over_the_network):
        self.key = key
        self.transport = transport
        self.remaining = None

    def get(self, path, read, **parameters):
        """One call, its answer read by `read`; any failure names only the path (#16, #32 §3)."""
        try:
            body, headers = self.transport(path, parameters, {"accept": "application/json", "X-API-KEY": self.key})
            self.remaining = remaining_of(headers)
            return read(body)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise NoSuchRecord(f"DoesTheDogDie has nothing at {path}.") from None
            raise NotAnswering(f"DoesTheDogDie failed on {path}.") from None
        except Exception:
            raise NotAnswering(f"DoesTheDogDie failed on {path}.") from None

    def answer(self, value):
        return Answer(value, self.remaining)

    def detail(self, item_id):
        return self.get(f"/items/{item_id}", dtdd.snapshot_from)

    def record(self, item_id):
        """The snapshot of one record by its id, of any item type: one already matched, or one a person pasted (#32 §5)."""
        return self.answer(self.detail(item_id))

    def lookup(self, tmdb_id, title, year):
        """A film's snapshot by #20 §7's rule; `items[0]` is never trusted, as TMDB's `results[0]` isn't (#25)."""
        fetched = {}

        def details(records):
            for record in records:
                if record.item_id not in fetched:
                    fetched[record.item_id] = self.detail(record.item_id)
            return dtdd.most_voted(fetched[record.item_id] for record in records)

        by_id = details([record for record in self.get("/items", dtdd.records_from, tmdb=tmdb_id) if record.item_type == dtdd.MOVIE])
        if by_id is not None and by_id.counts:
            return self.answer(by_id)
        candidates = self.get("/items", dtdd.records_from, q=title)
        by_title = details([record for record in candidates if dtdd.accepted_on_retry(record, title, year)])
        if by_title is not None and by_title.counts:
            return self.answer(by_title)
        # Uncovered: on the empty record the id found, if any (#20 §7).
        return self.answer(by_id or dtdd.NO_MATCH)

    def vocabulary(self):
        """Three calls, each answering with its whole list (#23, #62)."""
        topics = self.get("/topics", vocabulary.topics_from)
        categories = self.get("/topiccategories", vocabulary.categories_from)
        super_categories = self.get("/topicsupercategories", vocabulary.super_categories_from)
        return self.answer(vocabulary.assembled(topics, categories, super_categories))


def answer_from(transport):
    """Answer DoesTheDogDie from `transport` rather than the network, as the seeded instance does (#92, #102)."""
    global stand_in
    stand_in = transport


def dtdd_client():
    # The deployment never sets DEBUG, so it always reaches the real DoesTheDogDie (#50).
    transport = stand_in if settings.DEBUG and stand_in is not None else over_the_network
    return Client(settings.DTDD_API_KEY, transport)
