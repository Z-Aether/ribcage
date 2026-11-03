"""A reveal row opens as its film's read-only card under it, and closes to its row again (#29, #158)."""

import re

import pytest
from django.conf import settings
from django.urls import reverse

from ribcage.ballot.models import BallotRecord
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Note
from ribcage.triggers import watched
from tests.http.test_ballot_page import film
from tests.http.test_matched_topics import DOG, add, dtdd, signed_in, vocabulary  # noqa: F401
from tests.http.test_phase import walk_to

HTMX = {"HX-Request": "true"}


def mark(voter, suggestion, **fields):
    BallotRecord.objects.create(voter=voter, suggestion=suggestion, **fields)


def opened(client, suggestion, **query):
    return client.get(reverse("reveal_card"), {"suggestion": suggestion.pk, **query}, headers=HTMX)


def card_of(text):
    return re.search(r'<article class="film-card is-open".*?</article>', text, re.S)[0]


def close_button(text):
    return re.search(r'<button type="button" class="film-card__toggle"[^>]*>', text)[0]


@pytest.fixture
def revealed(voters):
    walk_to(Phase.PICK)
    hanna = voters["Hanna"]
    return {
        "hanna": hanna,
        "ada": voters["ada"],
        "dani": voters["Dani"],
        "one": film(hanna, "One"),
        "two": film(hanna, "Two"),
        "dropped": film(hanna, "Dropped", Approval.DROPPED),
    }


def approved_with_dog_death(voters):
    heavy = add(voters["Hanna"], "Heavy", dog=(12, 1))
    heavy.approval = Approval.APPROVED
    heavy.save()
    return heavy


def test_a_row_opens_as_its_card_in_the_tbody_that_holds_it(revealed):
    data = revealed

    text = opened(signed_in(data["ada"]), data["one"]).text

    assert f'<tbody class="reveal__group" id="reveal-film-{data["one"].pk}" data-scroll-here>' in text
    assert f'<tr class="reveal__row is-open" data-suggestion="{data["one"].pk}">' in text
    assert f'<tr class="reveal__detail" id="reveal-card-{data["one"].pk}">' in text
    assert 'aria-expanded="true"' in text and f'aria-controls="reveal-card-{data["one"].pk}"' in text
    assert re.search(r'<h3 class="film-card__title"><button[^>]*>One</button>', card_of(text))


def test_the_card_holds_no_phase_bar_whatever_the_ballot_says(revealed):
    data = revealed
    mark(data["ada"], data["one"], score=3, seen_it=True)
    mark(data["dani"], data["one"], vetoed=True)
    Note.objects.create(suggestion=data["one"], author=data["dani"], text="Not for me.")

    text = opened(signed_in(data["ada"]), data["one"]).text

    for absent in ("phase-bar--reveal", "reveal-chip", "reveal-points", "across the room", "didn't vote", "point</b>", "points</b>"):
        assert absent not in text
    # The row above it still shows every score; the notes still mark the veto and who has seen it.
    assert "Not for me." in card_of(text) and "vetoed by Dani" in card_of(text) and "has seen it" in card_of(text)


def test_the_card_is_read_only_and_lists_the_viewers_own_note_like_anyones(revealed):
    data = revealed
    Note.objects.create(suggestion=data["one"], author=data["ada"], text="My own words.")
    Note.objects.create(suggestion=data["one"], author=data["dani"], text="Danis words.")
    mark(data["ada"], data["one"], score=2, seen_it=True)

    card = card_of(opened(signed_in(data["ada"]), data["one"]).text)

    assert "My own words." in card and "Danis words." in card
    for absent in ("note-box", "<textarea", "runtime__pencil", "withdraw", "vote-bar", "seen-toggle", 'type="checkbox"', "<form"):
        assert absent not in card


def test_the_card_carries_the_pitch_first_and_who_suggested_it(revealed):
    data = revealed
    Note.objects.create(suggestion=data["one"], author=data["dani"], text="After.")
    Note.objects.create(suggestion=data["one"], author=data["hanna"], text="The pitch.")

    card = card_of(opened(signed_in(data["ada"]), data["one"]).text)

    assert card.index("The pitch.") < card.index("After.")
    assert "suggested by" in card and "Hanna" in card


def test_closing_answers_the_row_alone(revealed):
    data = revealed

    text = opened(signed_in(data["ada"]), data["one"], close="1").text

    assert f'<tbody class="reveal__group" id="reveal-film-{data["one"].pk}">' in text
    assert f'<tr class="reveal__row" data-suggestion="{data["one"].pk}">' in text
    assert 'aria-expanded="false"' in text
    assert "reveal__detail" not in text and "film-card" not in text and "data-scroll-here" not in text


def test_opening_another_row_draws_the_open_one_closed_out_of_band(revealed):
    data = revealed

    text = opened(signed_in(data["ada"]), data["two"], closes=data["one"].pk).text

    assert text.count("<tbody") == 2 and text.count("reveal__detail") == 1
    other = text[text.index(f'<tbody class="reveal__group" id="reveal-film-{data["one"].pk}"') :]
    assert other.startswith(f'<tbody class="reveal__group" id="reveal-film-{data["one"].pk}" hx-swap-oob="outerHTML">')
    assert "film-card" not in other and "data-scroll-here" not in other
    assert f'id="reveal-card-{data["two"].pk}"' in text


def test_naming_the_open_row_or_a_film_that_is_not_there_as_closed_adds_no_second_row(revealed):
    data = revealed

    assert opened(signed_in(data["ada"]), data["one"], closes=data["one"].pk).text.count("<tbody") == 1
    assert opened(signed_in(data["ada"]), data["one"], closes=data["dropped"].pk).text.count("<tbody") == 1


def test_the_cards_title_closes_it_by_a_request_that_keeps_the_sort(revealed):
    data = revealed
    dani = data["dani"].pk

    button = close_button(opened(signed_in(data["ada"]), data["one"], sort=f"-{dani}").text)

    assert f'hx-get="/reveal/card/?suggestion={data["one"].pk}&amp;close=1&amp;sort=-{dani}"' in button
    assert 'hx-target="closest tbody"' in button and 'hx-swap="outerHTML"' in button


def test_a_card_opened_under_reversed_points_keeps_it_and_the_page_carries_it(revealed):
    data = revealed
    button = close_button(opened(signed_in(data["ada"]), data["one"], sort="-points").text)

    assert f'hx-get="/reveal/card/?suggestion={data["one"].pk}&amp;close=1&amp;sort=-points"' in button
    assert 'data-sort="-points"' in signed_in(data["ada"]).get("/", {"sort": "-points"}).text


@pytest.mark.parametrize("sort,kept", [("film", "film"), ("-film", "-film"), ("-points", "-points"), ("points", ""), ("", ""), ("bogus", ""), ("9999", "")])
def test_an_unknown_sort_is_kept_as_points_in_the_close_link(revealed, sort, kept):
    button = close_button(opened(signed_in(revealed["ada"]), revealed["one"], sort=sort).text)

    assert button.count(f"&amp;sort={kept}\"") == 1


def test_the_page_marks_its_matrix_for_the_server_to_open_and_names_each_rows_button(revealed):
    data = revealed

    page = signed_in(data["ada"]).get("/", {"sort": "film"}).text

    assert 'data-sort="film"' in page and "data-reveal" in page and f'data-card-at="{reverse("reveal_card")}"' in page
    assert re.search(r'<button type="button" class="reveal__open" aria-expanded="false"><span class="reveal__title-line">One', page)
    assert page.count('<tbody class="reveal__group"') == 2 and "components/reveal-card" in page


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE, Phase.VOTE])
def test_before_the_reveal_the_route_reloads_the_tab_into_the_phase_and_shows_no_score(voters, phase):
    hanna, ada = voters["Hanna"], voters["ada"]
    one = film(hanna, "One")
    mark(ada, one, score=3)
    walk_to(phase)

    response = opened(signed_in(ada), one)

    assert (response.status_code, response.headers["HX-Redirect"], response.text) == (200, "/", "")


def test_a_plain_get_goes_to_the_phase_page(revealed):
    response = signed_in(revealed["ada"]).get(reverse("reveal_card"), {"suggestion": revealed["one"].pk})

    assert (response.status_code, response.headers["Location"]) == (302, "/")


def test_a_film_dropped_or_unknown_reloads_the_tab(revealed):
    for named in [revealed["dropped"].pk, 99999, "x", ""]:
        response = signed_in(revealed["ada"]).get(reverse("reveal_card"), {"suggestion": named}, headers=HTMX)

        assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")


def test_the_route_reads_and_refuses_a_post(revealed):
    response = signed_in(revealed["ada"]).post(reverse("reveal_card"), {"suggestion": revealed["one"].pk}, headers=HTMX)

    assert response.status_code == 405


def test_in_pick_the_card_carries_the_section_with_the_viewers_matched_topics_and_its_credit(voters, vocabulary):  # noqa: F811
    walk_to(Phase.PICK)
    heavy = approved_with_dog_death(voters)
    watched.set_ticked(voters["ada"], DOG, True)

    card = card_of(opened(signed_in(voters["ada"]), heavy).text)

    section = re.search(r'<section class="film-card__dtdd.*?</section>', card, re.S)[0]
    assert "data-dtdd" in section and "dog death" in section and "12 yes / 1 no" in section
    assert section.count("Powered by DoesTheDogDie.com") == 1
    # The full list is fetched when asked for, and the match can't be corrected: nothing is written after the reveal.
    assert 'hx-get="/dtdd/?suggestion=' in section
    assert "dtdd__correct" not in section and "dtdd/match" not in section
    assert "has-trigger-icon" in card


def test_the_matched_topics_are_the_viewers_own_list_alone(voters, vocabulary):  # noqa: F811
    walk_to(Phase.PICK)
    heavy = approved_with_dog_death(voters)
    watched.set_ticked(voters["ada"], DOG, True)

    card = card_of(opened(signed_in(voters["Dani"]), heavy).text)

    assert "dtdd__matched" not in card and "has-trigger-icon" not in card


def test_in_run_the_card_carries_no_trigger_content(voters, vocabulary):  # noqa: F811
    walk_to(Phase.RUN)
    # Stored since the purge, so only the phase keeps it off the card (#106).
    heavy = approved_with_dog_death(voters)
    mark(voters["ada"], heavy, score=2)
    watched.set_ticked(voters["ada"], DOG, True)

    text = opened(signed_in(voters["ada"]), heavy).text

    assert "reveal__detail" in text and "data-dtdd" not in text and "DoesTheDogDie" not in text and "has-trigger-icon" not in text
    assert "phase-bar--reveal" not in text and "across the room" not in text


def test_the_scripts_leave_a_reveal_card_to_the_reveals_own():
    cards = (settings.BASE_DIR / "ribcage/static/components/film-card.js").read_text(encoding="utf-8")
    own = (settings.BASE_DIR / "ribcage/static/components/reveal-card.js").read_text(encoding="utf-8")

    assert cards.count("[data-reveal]") == 3
    assert "Escape" in own and "closes" in own and "scrollLeft" not in own
