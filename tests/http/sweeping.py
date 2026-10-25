"""The sweep that the DoesTheDogDie credit and watched-list privacy invariants share: every page and every card fragment, as each viewer meets them (#112, #113)."""

from datetime import UTC, datetime
from typing import NamedTuple

from django.urls import reverse

from ribcage.suggestions.models import Suggestion
from ribcage.triggers import correction, stored
from ribcage.triggers.dtdd import Record, Snapshot, TopicCount
from tests.dtdd import VOCABULARY
from tests.http.routes import ADMIN, FRAGMENTS, VOTER, pages_of

RECORD, TOPIC, GROUP, DESCRIPTION, KEYWORDS = "RECORDSENTINEL", "TOPICSENTINEL", "GROUPSENTINEL", "DESCRIPTIONSENTINEL", "KEYWORDSSENTINEL"
YES, NO = 7771, 7772
DOG, CAT, JUMP = 153, 158, 200
HTMX = {"HX-Request": "true"}
AT = datetime(2026, 10, 24, tzinfo=UTC)


def sentinel_vocabulary():
    topics = [
        {**topic, "minimalName": f"{TOPIC}{topic['id']}", "description": f"{DESCRIPTION}{topic['id']}", "keywords": f"{KEYWORDS}{topic['id']}"} for topic in VOCABULARY["/topics"]
    ]
    groups = [{**group, "name": f"{GROUP}{group['id']}"} for group in VOCABULARY["/topicsupercategories"]]
    return {**VOCABULARY, "/topics": topics, "/topicsupercategories": groups}


def add(voter, title, approval, counted=True, yes=YES, no=NO):
    suggestion = Suggestion.objects.create(title=title, suggester=voter, suggester_name=voter.display_name, approval=approval, runtime=100)
    if counted:
        counts = tuple(TopicCount(topic, yes, no) for topic in (DOG, CAT, JUMP))
        stored.store_lookup(suggestion, Snapshot(Record(suggestion.pk, f"{RECORD}{suggestion.pk}", 2000, "Movie"), counts), AT)
    return suggestion


class Answer(NamedTuple):
    where: str
    # The fragment that gave it, or None for a page.
    fragment: object
    text: str

    @property
    def part(self):
        return self.fragment is not None and self.fragment.part


def pages():
    return [(path, VOTER) for path, _ in pages_of(VOTER)] + [(path, ADMIN) for path, _ in pages_of(ADMIN)]


def sweep(viewers, films, also=()):
    """Every page, then each of `also` (more pages, as (path, viewer)), then every card's fragments, each as an Answer."""
    for path, viewer in [*pages(), *also]:
        yield Answer(f"{viewer} {path}", None, viewers[viewer].get(path).text)
    saved = correction.signed(Snapshot(Record(films[0].pk, f"{RECORD}used", 2001, "Movie"), (TopicCount(DOG, YES, NO),)), films[0].pk)
    for fragment in FRAGMENTS:
        for film in films:
            snapshot = saved if film is films[0] else correction.signed(Snapshot(Record(film.pk, f"{RECORD}used", 2001, "Movie"), ()), film.pk)
            parameters = {key: value.format(film=film.pk, snapshot=snapshot, topic=DOG) for key, value in fragment.parameters.items()}
            url = reverse(fragment.route)
            client = viewers[fragment.viewer]
            if fragment.method == "GET":
                response = client.get(url, parameters, headers=HTMX)
            else:
                response = client.post(url, parameters, headers=HTMX)
            yield Answer(f"{fragment.route} {fragment.method} {fragment.parameters} (part={fragment.part})", fragment, response.text)
