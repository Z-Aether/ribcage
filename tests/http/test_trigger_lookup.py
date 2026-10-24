"""A suggested film's trigger data: looked up once its add commits, never inside the write lock, and shown on the Films tab (#32, #78, #102)."""

import html
import re

import pytest
from django.db import connection

from ribcage.films import signed
from ribcage.identity.models import Voter
from ribcage.suggestions.models import Suggestion
from ribcage.triggers import client as dtdd_client
from ribcage.triggers import fetch, stored
from ribcage.triggers.dtdd import Record, Snapshot, TopicCount
from ribcage.triggers.models import Topic, TriggerData
from ribcage.triggers.status import State
from ribcage.triggers.vocabulary import UNCATEGORIZED, SuperCategory, Vocabulary
from ribcage.triggers.vocabulary import Topic as VocabularyTopic
from tests.dtdd import VOCABULARY_PATHS, Dtdd, detail, item
from tests.films import CABINET_OF_CURIOSITIES, THE_SHINING, a_tmdb_film
from tests.http.signing_in import PASSWORD

SUGGEST = "/suggest/"
TAB = "/console/films/"
HTMX = {"HX-Request": "true"}
SHINING = item(12189, "The Shining", 1980)
SHINING_DETAIL = detail(SHINING, (153, 3, 1), (200, 40, 2))


def shining_dtdd(**options):
    return Dtdd(by_tmdb={THE_SHINING.tmdb_id: [SHINING]}, details=[SHINING_DETAIL], **options)


@pytest.fixture
def dtdd(monkeypatch):
    # The tests run with DEBUG off, so the real transport is the one the client reaches.
    def install(transport):
        monkeypatch.setattr(dtdd_client, "over_the_network", transport)
        return transport

    return install


@pytest.fixture
def hanna(client, voters):
    client.force_login(voters["Hanna"])
    return client


def add(client, film=THE_SHINING, pitch="Heeere's Johnny."):
    return client.post(SUGGEST, {"film": signed.signed(film), "pitch": pitch, "runtime": str(film.runtime)}, headers=HTMX)


def add_by_hand(client):
    form = {"by_hand": "1", "title": "Cabinet of Curiosities", "year": "", "pitch": "The Autopsy.", "runtime": "47"}
    return client.post(SUGGEST, form, headers=HTMX)


def status_of(suggestion):
    return stored.statuses_of([suggestion])[suggestion.pk]


def test_adding_a_tmdb_film_stores_its_match_and_snapshot_after_the_add_commits(hanna, dtdd, django_capture_on_commit_callbacks):
    transport = dtdd(shining_dtdd())

    with django_capture_on_commit_callbacks() as waiting:
        add(hanna)
    # Nothing goes online inside the add; the lookup waits for its commit.
    assert transport.paths == []
    assert not TriggerData.objects.exists()
    for callback in waiting:
        callback()

    shining = Suggestion.objects.get(tmdb_id=THE_SHINING.tmdb_id)
    status = status_of(shining)
    assert (status.state, status.match, status.set_by) == (State.MATCHED, SHINING["id"], "")
    assert status.fetched.snapshot == Snapshot(Record(12189, "The Shining", 1980, "Movie"), (TopicCount(153, 3, 1), TopicCount(200, 40, 2)))


def test_the_voter_still_lands_on_the_pool(hanna, dtdd, django_capture_on_commit_callbacks):
    dtdd(shining_dtdd())

    with django_capture_on_commit_callbacks(execute=True):
        response = add(hanna)

    assert response.headers["HX-Redirect"] == "/"


@pytest.mark.parametrize("error", [TimeoutError(), ConnectionError(), ValueError("malformed")])
def test_dtdd_failing_leaves_the_film_added_and_not_fetched(hanna, dtdd, django_capture_on_commit_callbacks, error):
    dtdd(shining_dtdd(error=error))

    with django_capture_on_commit_callbacks(execute=True):
        response = add(hanna)

    assert response.headers["HX-Redirect"] == "/"
    shining = Suggestion.objects.get(tmdb_id=THE_SHINING.tmdb_id)
    assert status_of(shining).state is State.NOT_FETCHED


def test_a_failure_after_the_vocabulary_keeps_the_vocabulary_and_leaves_the_film_not_fetched(hanna, dtdd, django_capture_on_commit_callbacks):
    def fail_on_items(path):
        if path.startswith("/items"):
            raise TimeoutError

    dtdd(shining_dtdd(on_call=fail_on_items))

    with django_capture_on_commit_callbacks(execute=True):
        add(hanna)

    assert Topic.objects.count() == 3
    assert status_of(Suggestion.objects.get()).state is State.NOT_FETCHED


def test_a_film_added_by_hand_looks_nothing_up(hanna, dtdd, django_capture_on_commit_callbacks):
    transport = dtdd(shining_dtdd())

    with django_capture_on_commit_callbacks(execute=True):
        response = add_by_hand(hanna)

    assert response.headers["HX-Redirect"] == "/"
    assert transport.paths == []
    assert not Topic.objects.exists()
    assert status_of(Suggestion.objects.get()).state is State.NO_MATCH


def test_a_lookup_without_a_vocabulary_fetches_the_vocabulary_first(hanna, dtdd, django_capture_on_commit_callbacks):
    transport = dtdd(shining_dtdd())

    with django_capture_on_commit_callbacks(execute=True):
        add(hanna)

    assert transport.paths == [*VOCABULARY_PATHS, "/items", "/items/12189"]
    vocabulary = stored.stored_vocabulary()
    assert [topic.label for topic in vocabulary.topics] == ["dog death", "cat death", "jump scares"]
    assert [(group.name, [topic.topic_id for topic in topics]) for group, topics in vocabulary.groups] == [("Animals", [153, 158]), ("Scary stuff", [200])]


def test_a_stored_topic_that_resolves_nowhere_reads_back_as_uncategorized_after_dtdds_own_other(db):
    other = SuperCategory(9, "Other")
    vocabulary = Vocabulary(
        (
            VocabularyTopic(1, "lost", "", "", UNCATEGORIZED),
            VocabularyTopic(2, "misc", "", "", other),
        ),
        (other,),
    )

    stored.replace_vocabulary(vocabulary)

    assert [(group.name, [topic.topic_id for topic in topics]) for group, topics in stored.stored_vocabulary().groups] == [("Other", [2]), ("Uncategorized", [1])]


def test_a_lookup_with_a_vocabulary_leaves_it_alone(hanna, dtdd, django_capture_on_commit_callbacks):
    first = dtdd(Dtdd(by_tmdb={1: []}))
    with django_capture_on_commit_callbacks(execute=True):
        add(hanna, a_tmdb_film(1, "Pulse"))
    assert first.paths[:3] == VOCABULARY_PATHS
    transport = dtdd(shining_dtdd())

    with django_capture_on_commit_callbacks(execute=True):
        add(hanna, pitch="Again.")

    assert transport.paths == ["/items", "/items/12189"]


def test_a_vocabulary_that_fails_leaves_none_and_the_film_not_fetched(hanna, dtdd, django_capture_on_commit_callbacks):
    def fail_on_super_categories(path):
        if path == "/topicsupercategories":
            raise TimeoutError

    transport = dtdd(shining_dtdd(on_call=fail_on_super_categories))

    with django_capture_on_commit_callbacks(execute=True):
        add(hanna)

    assert "/items" not in transport.paths
    assert not Topic.objects.exists()
    assert status_of(Suggestion.objects.get()).state is State.NOT_FETCHED


def test_the_vocabulary_is_replaced_whole(db):
    stored.replace_vocabulary(Vocabulary((), ()))
    first = Dtdd()
    stored.replace_vocabulary(dtdd_client.Client("key", first).vocabulary().value)
    trimmed = {**first.vocabulary, "/topics": first.vocabulary["/topics"][2:]}

    stored.replace_vocabulary(dtdd_client.Client("key", Dtdd(vocabulary=trimmed)).vocabulary().value)

    assert list(Topic.objects.values_list("topic_id", "label", "super_category_name")) == [(200, "jump scares", "Scary stuff")]


def test_trigger_data_goes_with_its_suggestion(voters, dtdd):
    shining = Suggestion.objects.suggest(voters["ada"], THE_SHINING, "Pitch.")
    fetch.look_up(shining, dtdd_client.Client("key", shining_dtdd()))
    assert TriggerData.objects.filter(suggestion=shining).exists()

    shining.delete()

    assert not TriggerData.objects.exists()


def test_an_uncovered_film_keeps_the_empty_record_it_was_matched_to(voters):
    werewolf = Suggestion.objects.suggest(voters["ada"], a_tmdb_film(894205, "Werewolf by Night"), "Pitch.")
    empty = item(1210242, "Werewolf By Night", 2022)

    fetch.look_up(werewolf, dtdd_client.Client("key", Dtdd(by_tmdb={894205: [empty]}, details=[detail(empty)])))

    status = status_of(werewolf)
    assert (status.state, status.match) == (State.UNCOVERED, 1210242)


def test_a_film_dtdd_has_nothing_for_is_uncovered_with_no_match(voters):
    pulse = Suggestion.objects.suggest(voters["ada"], a_tmdb_film(1, "Pulse"), "Pitch.")

    fetch.look_up(pulse, dtdd_client.Client("key", Dtdd()))

    status = status_of(pulse)
    assert (status.state, status.match) == (State.UNCOVERED, None)


# The Films tab


def ledger_statuses(page):
    found = re.findall(r'<td class="films-ledger__dtdd films-ledger__dtdd--([a-z-]+)">(.*?)</td>', page)
    return [(state, html.unescape(words)) for state, words in found]


@pytest.fixture
def every_state(voters):
    ada = voters["ada"]
    shining = Suggestion.objects.suggest(ada, THE_SHINING, "Pitch.")
    werewolf = Suggestion.objects.suggest(ada, a_tmdb_film(894205, "Werewolf by Night"), "Pitch.")
    Suggestion.objects.suggest(ada, a_tmdb_film(1078605, "Weapons"), "Pitch.")
    Suggestion.objects.suggest(ada, CABINET_OF_CURIOSITIES, "Pitch.")
    # The Shining's counts hold a topic the vocabulary doesn't name, which stays off the count (#62).
    shining_detail = detail(SHINING, (153, 3, 1), (200, 40, 2), (999, 5, 0))
    fetch.look_up(shining, dtdd_client.Client("key", Dtdd(by_tmdb={THE_SHINING.tmdb_id: [SHINING]}, details=[shining_detail])))
    fetch.look_up(werewolf, dtdd_client.Client("key", Dtdd()))


def test_each_row_shows_its_dtdd_status(admin, every_state):
    page = admin.get(TAB).text

    assert ledger_statuses(page) == [("no-match", "no match"), ("not-fetched", "not fetched"), ("uncovered", "uncovered"), ("matched", "2 topics")]
    assert '<th scope="col"><abbr title="DoesTheDogDie">DTDD</abbr></th>' in page


def test_the_ledger_carries_one_credit_line_to_doesthedogdie(admin, every_state):
    page = admin.get(TAB).text
    tab = page.split('<footer class="site-footer">')[0]

    credit = re.search(r'<p class="films-credit">(.*?)</p>', tab, re.S)[1]
    assert credit == '<a href="https://www.doesthedogdie.com/">Powered by DoesTheDogDie.com</a>'
    # Each opened card under a row carries its own, so the ledger's is the one outside them (#103).
    outside_the_cards = re.sub(r'<tr class="ledger__detail".*?</tr>', "", tab, flags=re.S)
    assert outside_the_cards.count("Powered by DoesTheDogDie.com") == 1


def test_an_empty_ledger_shows_no_dtdd_data_and_no_credit_line(admin):
    page = admin.get(TAB).text

    assert 'class="films-credit"' not in page


def test_the_column_shows_nothing_personal(admin, every_state):
    page = admin.get(TAB).text

    statuses = " ".join(words for _, words in ledger_statuses(page))
    assert "Ada" not in statuses and "ada" not in statuses


# Never inside the write lock


@pytest.mark.django_db(transaction=True)
def test_no_dtdd_call_is_made_while_the_adds_transaction_is_open(client, dtdd):
    # A transactional test, so the add's transaction is the real outermost one and its commit really runs the lookup.
    asked_inside = []
    transport = dtdd(shining_dtdd(on_call=lambda path: asked_inside.append(connection.in_atomic_block)))
    client.force_login(Voter.objects.create_voter("Hanna", PASSWORD))

    response = add(client)

    assert response.headers["HX-Redirect"] == "/"
    assert transport.paths == [*VOCABULARY_PATHS, "/items", "/items/12189"]
    assert asked_inside == [False] * len(transport.paths)
    assert status_of(Suggestion.objects.get()).state is State.MATCHED
