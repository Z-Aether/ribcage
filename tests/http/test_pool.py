"""The pool as voters read it on the SUGGEST and APPROVE pages (#27, #87)."""

import re
from itertools import pairwise

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.identity.removal import remove
from ribcage.phase.history import move
from ribcage.phase.order import PHASES, Phase
from ribcage.suggestions.models import Approval, Suggestion
from tests.films import a_tmdb_film

POOL_PHASES = [Phase.SUGGEST, Phase.APPROVE]
LATER_PHASES = [Phase.VOTE, Phase.PICK, Phase.RUN]


def walk_to(phase):
    for before, after in pairwise(PHASES[: PHASES.index(phase) + 1]):
        move(before, after)


@pytest.fixture
def voter_client(client, voters):
    client.force_login(voters["Hanna"])
    return client


def suggest(voters, titles, suggester="ada"):
    return [
        Suggestion.objects.suggest(voters[suggester], a_tmdb_film(1000 + index, title), f"The pitch for {title}.")
        for index, title in enumerate(titles, Suggestion.objects.count())
    ]


def main(page):
    # Without the CSRF token, which is masked afresh on every render.
    return re.sub(r'name="csrfmiddlewaretoken" value="\w+"', "", re.search(r"<main>.*</main>", page, re.S)[0])


def without_the_pencil(page, suggestion):
    return re.sub(rf' <a class="runtime__pencil" id="runtime-{suggestion.pk}"[^>]*>✎</a>', "", page)


def titles_shown(page):
    return re.findall(r'class="film-card__toggle"[^>]*>([^<]+)</button>', page)


@pytest.mark.parametrize("phase", POOL_PHASES)
def test_the_pool_is_shown_newest_first(voter_client, voters, phase):
    suggest(voters, ["First", "Second", "Third"])
    walk_to(phase)

    assert titles_shown(voter_client.get("/").text) == ["Third", "Second", "First"]


@pytest.mark.parametrize("phase", POOL_PHASES)
def test_the_pool_shows_no_mark_of_approval(voter_client, voters, phase):
    suggestions = suggest(voters, ["The Thing", "Cube", "Coco"])
    walk_to(phase)
    undecided = main(voter_client.get("/").text)

    approved, dropped = suggestions[1:]
    Suggestion.objects.filter(pk=approved.pk).update(approval=Approval.APPROVED)
    Suggestion.objects.filter(pk=dropped.pk).update(approval=Approval.DROPPED)
    decided = main(voter_client.get("/").text)

    # In SUGGEST an approved film's runtime pencil is absent, with no word on why: no mark, by design (#34, #90).
    expected = without_the_pencil(undecided, approved) if phase is Phase.SUGGEST else undecided
    assert decided == expected
    assert not re.search(r"approved|dropped|undecided|ballot", decided, re.I)


@pytest.mark.parametrize("phase", POOL_PHASES)
def test_each_card_shows_its_suggester_and_the_pitch_ahead_of_the_other_notes(voter_client, voters, phase):
    (suggestion,) = suggest(voters, ["The Thing"])
    suggestion.notes.create(author=voters["Dani"], text="Lights off for this one.")
    walk_to(phase)

    page = voter_client.get("/").text

    assert '<span class="film-card__suggester">ada</span>' in page
    assert page.index("note--pitch") < page.index("The pitch for The Thing.") < page.index("Lights off for this one.")


def test_a_removed_suggesters_card_says_who_suggested_it_marked_removed(voter_client, voters):
    suggest(voters, ["The Thing"])

    remove(voters["ada"])

    page = voter_client.get("/").text
    assert '<span class="film-card__suggester is-removed">ada</span> <span class="removed-tag">removed</span>' in page
    assert "The pitch for The Thing." in page


@pytest.mark.parametrize("phase", POOL_PHASES)
def test_the_page_makes_as_many_queries_for_a_large_pool_as_for_a_small_one(voter_client, voters, phase):
    walk_to(phase)

    def queries_for_the_page():
        with CaptureQueriesContext(connection) as captured:
            assert voter_client.get("/").status_code == 200
        return len(captured)

    for suggestion in suggest(voters, ["One"]):
        suggestion.notes.create(author=voters["Hanna"], text="I'm in.")
    small = queries_for_the_page()
    for suggestion in suggest(voters, ["Two", "Three", "Four", "Five"], suggester="Dani"):
        suggestion.notes.create(author=voters["Hanna"], text="I'm in.")
        suggestion.notes.create(author=voters["ada"], text="Me too.")

    assert queries_for_the_page() == small


@pytest.mark.parametrize("phase", POOL_PHASES)
def test_an_empty_pool_says_so(voter_client, phase):
    walk_to(phase)

    page = voter_client.get("/").text

    assert "No films have been suggested." in page
    assert "<article" not in main(page)


@pytest.mark.parametrize("phase", LATER_PHASES)
def test_from_vote_on_there_is_no_pool(voter_client, voters, phase):
    suggest(voters, ["The Thing"])
    walk_to(phase)

    page = voter_client.get("/").text

    assert "The Thing" not in page
    assert "film-card" not in main(page)
