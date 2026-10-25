"""My warnings' films under each topic: the pool or the ballot, most yes first, one read however large the pool (#109)."""

import html
import re
from datetime import UTC, datetime

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.triggers import stored
from ribcage.triggers.dtdd import Record, Snapshot, TopicCount
from tests.http.test_my_warnings import CAT, DOG, JUMP, PAGE, TICK, HTMX, ada, browser, dtdd, vocabulary  # noqa: F401
from tests.http.test_phase import walk_to

AT = datetime(2026, 10, 24, tzinfo=UTC)


def add(voter, title, approval=Approval.UNDECIDED, **votes):
    """A suggestion whose snapshot counts each topic `(yes, no)`: dog, cat, jump."""
    suggestion = Suggestion.objects.create(title=title, suggester=voter, suggester_name=voter.display_name, approval=approval, runtime=100)
    counts = tuple(TopicCount({"dog": DOG, "cat": CAT, "jump": JUMP}[name], yes, no) for name, (yes, no) in votes.items())
    stored.store_lookup(suggestion, Snapshot(Record(suggestion.pk, title, 2000, "Movie"), counts), AT)
    return suggestion


def films_of(page, topic):
    row = re.search(rf'<li id="topic-{topic}".*?</li>', page, re.S)[0]
    return html.unescape(re.search(r'<p class="warnings__films[^"]*">([^<]*)</p>', row)[1])


@pytest.fixture
def pool(ada):
    add(ada, "Few", dog=(9, 0))
    add(ada, "Many", Approval.APPROVED, dog=(40, 3))
    add(ada, "Alpha", Approval.DROPPED, dog=(9, 0), cat=(5, 0))
    add(ada, "Thin", dog=(4, 0), cat=(5, 5))


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE])
def test_through_approve_every_film_is_named_undecided_and_dropped_too(browser, pool, phase):
    walk_to(phase)
    page = browser.get(PAGE).text

    assert films_of(page, DOG) == "Many · Alpha · Few"
    assert films_of(page, CAT) == "Alpha"
    assert films_of(page, JUMP) == "no films in the pool"


@pytest.mark.parametrize("phase", [Phase.VOTE, Phase.PICK])
def test_from_vote_on_only_the_ballot_is_named_and_a_drop_is_not_revealed(browser, pool, phase):
    walk_to(phase)
    page = browser.get(PAGE).text

    assert films_of(page, DOG) == "Many"
    assert "Alpha" not in page and "Few" not in page
    assert films_of(page, CAT) == "no films on the ballot"
    assert films_of(page, JUMP) == "no films on the ballot"


def test_a_topic_no_film_carries_says_so_in_muted_ink(browser, pool):
    page = browser.get(PAGE).text

    assert films_of(page, JUMP) == "no films in the pool"
    assert 'class="warnings__films is-none"' in re.search(r'<li id="topic-200".*?</li>', page, re.S)[0]


def test_the_films_stay_out_of_the_search_text(browser, pool):
    page = browser.get(PAGE).text

    assert "many" not in re.search(r'<li id="topic-153"[^>]*data-search="([^"]*)"', page)[1]


def test_a_tick_answers_with_the_rows_films_so_the_morph_keeps_them(browser, pool):
    answer = browser.post(TICK, {"topic": str(DOG), "ticked": "1"}, headers=HTMX).text

    assert films_of(answer, DOG) == "Many · Alpha · Few"


def test_the_pages_queries_do_not_grow_with_the_pool(browser, ada, pool):
    def queries():
        with CaptureQueriesContext(connection) as seen:
            browser.get(PAGE)
        return len(seen)

    before = queries()
    for number in range(10):
        add(ada, f"More {number}", dog=(20, 0))

    assert queries() == before
