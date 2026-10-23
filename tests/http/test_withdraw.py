"""Withdraw on a voter's own card: a click arms it, an inline confirm withdraws, and only in SUGGEST (#27, #34, #85, #89)."""

import html
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Note, Suggestion
from ribcage.suggestions.views import withdraw
from tests.films import a_tmdb_film
from tests.http.test_phase import walk_to
from tests.http.test_phase_check import send

WITHDRAW = "/withdraw/"
HTMX = {"HX-Request": "true"}
OUTSIDE_THE_WINDOW = [Phase.APPROVE, Phase.VOTE, Phase.PICK, Phase.RUN]
PITCH = "The one with the kennel scene. Lights off."


@pytest.fixture
def the_thing(voters):
    # Hanna's suggestion, with her pitch and notes by ada and Dani.
    suggestion = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing"), PITCH)
    suggestion.notes.create(author=voters["ada"], text="Seen it twice.")
    suggestion.notes.create(author=voters["Dani"], text="I'm in.")
    return suggestion


@pytest.fixture
def cube(voters):
    # Dani's suggestion, which no withdraw of Hanna's may touch.
    suggestion = Suggestion.objects.suggest(voters["Dani"], a_tmdb_film(431, "Cube"), "Six strangers in a box.")
    suggestion.notes.create(author=voters["Hanna"], text="Yes please.")
    return suggestion


def signed_in(client, voter):
    client.force_login(voter)
    return client


@pytest.fixture
def hanna(client, voters):
    return signed_in(client, voters["Hanna"])


@pytest.fixture
def dani(client, voters):
    return signed_in(client, voters["Dani"])


def confirm(client, suggestion, headers=HTMX):
    return client.post(WITHDRAW, {"suggestion": suggestion if isinstance(suggestion, str) else suggestion.pk}, headers=headers)


def arm(client, suggestion, headers=HTMX, **extra):
    return client.get(WITHDRAW, {"suggestion": suggestion.pk, **extra}, headers=headers)


def still_there(suggestion):
    return Suggestion.objects.filter(pk=suggestion.pk).exists()


def approve(suggestion):
    Suggestion.objects.filter(pk=suggestion.pk).update(approval=Approval.APPROVED)


def text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def withdraw_region(page):
    found = re.search(r'<div class="withdraw[^"]*" data-withdraw>.*?</div>', page, re.S)
    return found[0] if found else None


def arms_on(page):
    """The suggestion of each card in the page that offers Withdraw…, armed or not."""
    cards = re.findall(r'<article class="film-card[^"]*" data-film-card data-suggestion="(\d+)"[^>]*>(.*?)</article>', page, re.S)
    return [int(pk) for pk, shown in cards if withdraw_region(shown)]


def test_withdraw_is_windowed_to_suggest():
    assert withdraw.phase_window == {Phase.SUGGEST}


def test_confirming_withdraws_the_suggestion_and_the_card_leaves_the_pool(hanna, the_thing, cube):
    response = confirm(hanna, the_thing)

    # An empty answer swaps the card out of the pool in place (#89).
    assert (response.status_code, response.text) == (200, "")
    assert not still_there(the_thing)
    assert still_there(cube)


def test_the_suggestions_notes_go_with_it(hanna, the_thing, cube):
    confirm(hanna, the_thing)

    assert not Note.objects.filter(suggestion=the_thing.pk).exists()
    assert list(Note.objects.values_list("text", flat=True).order_by("pk")) == ["Six strangers in a box.", "Yes please."]


def test_a_plain_confirm_withdraws_and_is_sent_to_the_phase_page(hanna, the_thing):
    response = confirm(hanna, the_thing, headers={})

    assert (response.status_code, response.headers["Location"]) == (302, "/")
    assert not still_there(the_thing)


def test_a_dropped_suggestion_nothing_holds_can_be_withdrawn(hanna, the_thing):
    Suggestion.objects.filter(pk=the_thing.pk).update(approval=Approval.DROPPED)

    confirm(hanna, the_thing)

    assert not still_there(the_thing)


@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
def test_an_htmx_confirm_outside_suggest_withdraws_nothing_and_reloads_the_tab(hanna, the_thing, phase):
    walk_to(phase)

    response = confirm(hanna, the_thing)

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")
    assert still_there(the_thing)


@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
def test_a_plain_confirm_outside_suggest_withdraws_nothing_and_is_sent_to_the_phase_page(hanna, the_thing, phase):
    walk_to(phase)

    response = confirm(hanna, the_thing, headers={})

    assert (response.status_code, response.headers["Location"]) == (302, "/")
    assert still_there(the_thing)


def test_another_voters_suggestion_is_refused_and_answered_with_its_card_offering_no_withdraw(dani, the_thing):
    response = confirm(dani, the_thing)

    assert still_there(the_thing)
    assert Note.objects.filter(suggestion=the_thing).count() == 3
    assert response.text.count("<article") == 1
    assert f'data-suggestion="{the_thing.pk}"' in response.text
    assert withdraw_region(response.text) is None


def test_an_approved_suggestion_is_refused_and_answered_with_its_card_offering_no_withdraw(hanna, the_thing):
    approve(the_thing)

    response = confirm(hanna, the_thing)

    assert still_there(the_thing)
    assert f'data-suggestion="{the_thing.pk}"' in response.text
    assert withdraw_region(response.text) is None


def test_a_repeated_confirm_is_harmless(hanna, the_thing, cube, voters):
    other = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(603, "The Matrix"), "Her second.")
    confirm(hanna, the_thing)

    response = confirm(hanna, the_thing)

    # The confirm names its suggestion, so the second finds nothing and takes nothing else (#89).
    assert (response.status_code, response.text) == (200, "")
    assert set(Suggestion.objects.all()) == {cube, other}
    assert Note.objects.count() == 3


@pytest.mark.parametrize("named", ["999", "not-a-number", ""])
def test_a_confirm_naming_no_suggestion_withdraws_nothing(hanna, the_thing, named):
    response = confirm(hanna, named)

    assert (response.status_code, response.text) == (200, "")
    assert still_there(the_thing)


@pytest.mark.parametrize("method", ["options", "trace", "put", "patch", "delete"])
@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.VOTE])
def test_the_withdraw_route_answers_every_method_but_get_head_and_post_with_405(hanna, the_thing, method, phase):
    walk_to(phase)

    response = send(hanna, method, WITHDRAW, f"suggestion={the_thing.pk}")

    assert response.status_code == 405
    assert still_there(the_thing)


# Arming


def test_arming_writes_nothing(hanna, the_thing):
    with CaptureQueriesContext(connection) as captured:
        response = arm(hanna, the_thing)

    assert response.status_code == 200
    assert [query["sql"] for query in captured if not query["sql"].lstrip().upper().startswith("SELECT")] == []
    assert still_there(the_thing)
    assert Note.objects.filter(suggestion=the_thing).count() == 3


def test_the_armed_confirm_names_the_suggestion_and_what_goes_with_it(hanna, the_thing):
    region = withdraw_region(arm(hanna, the_thing).text)

    assert f'<input type="hidden" name="suggestion" value="{the_thing.pk}">' in region
    assert "The Thing leaves the pool, and takes your pitch and 2 notes from the group with it." in text(region)
    assert re.search(r'<button type="submit">Withdraw The Thing</button>', region)


def test_armed_cancel_takes_the_arms_place_and_the_confirm_stands_after_what_goes(hanna, the_thing):
    region = withdraw_region(arm(hanna, the_thing).text)

    cancel = re.search(r'<a [^>]*class="button button--quiet withdraw__act withdraw__cancel"[^>]*>(.*?)</a>', region, re.S)
    assert text(cancel[1]) == "Cancel Withdraw…"
    assert region.index("withdraw__cancel") < region.index("leaves the pool") < region.index('type="submit"')


def test_cancel_disarms_and_offers_withdraw_again(hanna, the_thing):
    region = withdraw_region(arm(hanna, the_thing, cancel="").text)

    assert "leaves the pool" not in region
    assert 'type="submit"' not in region
    assert re.search(r">Withdraw…</a>", region)


def test_the_cancel_link_is_the_disarmed_address(hanna, the_thing):
    region = withdraw_region(arm(hanna, the_thing).text)

    assert f'hx-get="/withdraw/?suggestion={the_thing.pk}&amp;cancel"' in region


@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
def test_arming_outside_suggest_reloads_the_tab(hanna, the_thing, phase):
    walk_to(phase)

    response = arm(hanna, the_thing)

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")


def test_arming_another_voters_suggestion_arms_nothing(dani, the_thing):
    response = arm(dani, the_thing)

    # The act leaves the card, with no explanation (#27).
    assert (response.status_code, response.text) == (200, "")


def test_arming_an_approved_suggestion_arms_nothing(hanna, the_thing):
    approve(the_thing)

    assert arm(hanna, the_thing).text == ""


def test_arming_a_suggestion_that_is_gone_reloads_the_tab(hanna, the_thing):
    confirm(hanna, the_thing)

    response = arm(hanna, the_thing)

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")


def test_a_plain_arm_is_sent_to_the_phase_page_and_arms_nothing(hanna, the_thing):
    response = arm(hanna, the_thing, headers={})

    assert (response.status_code, response.headers["Location"]) == (302, "/")


# The pool


def test_in_suggest_withdraw_sits_on_the_voters_own_cards_alone(hanna, the_thing, cube):
    page = hanna.get("/").text

    assert arms_on(page) == [the_thing.pk]
    assert "leaves the pool" not in page


def test_in_suggest_withdraw_is_absent_from_an_approved_card(hanna, voters, the_thing):
    coco = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(354912, "Coco"), "Not horror, I know.")
    approve(the_thing)

    assert arms_on(hanna.get("/").text) == [coco.pk]


def test_in_approve_withdraw_is_absent_everywhere(hanna, the_thing):
    walk_to(Phase.APPROVE)

    page = hanna.get("/").text

    assert f'data-suggestion="{the_thing.pk}"' in page
    assert arms_on(page) == []
