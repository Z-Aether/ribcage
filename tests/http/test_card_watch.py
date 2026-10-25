"""The watch toggles on an opened card's full topic list, the card's way onto the watched list (#114)."""

import re

import pytest

from ribcage.phase.order import Phase
from ribcage.triggers import watched
from tests.http.test_matched_topics import RING, add, matched_rows, ringed, signed_in
from tests.http.test_my_warnings import CAT, DOG, HTMX, PAGE, WRITING, dtdd, vocabulary  # noqa: F401
from tests.http.test_phase import walk_to

LIST, WATCH = "/dtdd/", "/dtdd/watch/"


@pytest.fixture
def heavy(voters, vocabulary):  # noqa: F811
    return add(voters["Hanna"], "Heavy", dog=(12, 1), cat=(1, 0))


def watch(client, film, topic, on=True, **extra):
    return client.post(WATCH, {"suggestion": str(film.pk), "topic": str(topic), "ticked": "1" if on else "0"}, **extra)


def toggles(text):
    """Each topic row's toggle as (label, topic id, what it posts, pressed)."""
    return [
        (label, int(topic), int(ticked), pressed == "true")
        for label, topic, ticked, pressed in re.findall(
            r'class="dtdd__topic[^"]*"><span class="dtdd__label">([^<]+)</span>.*?name="topic" value="(\d+)">\s*<input type="hidden" name="ticked" value="(\d)">\s*<button[^>]*aria-pressed="(\w+)"',
            text,
            re.S,
        )
    ]


def test_the_fetched_list_offers_each_row_a_toggle_that_posts_the_topic_in_the_body(voters, heavy):
    fetched = signed_in(voters["ada"]).get(f"{LIST}?suggestion={heavy.pk}", headers=HTMX).text

    assert toggles(fetched) == [("dog death", DOG, 1, False), ("cat death", CAT, 1, False)]
    assert f'hx-post="{WATCH}"' in fetched and 'hx-target="closest .film-card__dtdd"' in fetched
    assert "?topic" not in fetched and "&topic" not in fetched


def test_a_row_on_the_list_reads_as_watched_and_its_toggle_unwatches(voters, heavy):
    watched.set_ticked(voters["ada"], DOG, True)
    fetched = signed_in(voters["ada"]).get(f"{LIST}?suggestion={heavy.pk}", headers=HTMX).text

    assert toggles(fetched) == [("dog death", DOG, 0, True), ("cat death", CAT, 1, False)]
    assert re.search(r'class="dtdd__topic is-watched"><span class="dtdd__label">dog death', fetched)


@pytest.mark.parametrize("phase", WRITING)
def test_watching_and_unwatching_store_and_remove_the_topic(voters, heavy, phase):
    walk_to(phase)
    ada = signed_in(voters["ada"])

    assert watch(ada, heavy, DOG, headers=HTMX).status_code == 200
    assert watched.ticked_ids(voters["ada"]) == {DOG}
    watch(ada, heavy, DOG, headers=HTMX)
    assert watched.ticked_ids(voters["ada"]) == {DOG}
    watch(ada, heavy, DOG, on=False, headers=HTMX)
    assert watched.ticked_ids(voters["ada"]) == set()


def test_the_answer_is_the_section_open_with_the_row_watched_the_matched_block_and_the_ring(voters, heavy):
    answer = watch(signed_in(voters["ada"]), heavy, DOG, headers=HTMX).text

    assert answer.lstrip().startswith("<section")
    details = re.search(r'<details class="dtdd__topics"[^>]*>', answer)[0]
    assert " open " in details and 'id="dtdd-topics-' in details and "hx-preserve" not in details
    assert toggles(answer) == [("dog death", DOG, 0, True), ("cat death", CAT, 1, False)]
    assert matched_rows(f'<article class="film-card" data-film-card data-suggestion="{heavy.pk}">{answer}</article>', heavy) == [("dog death", "12 yes / 1 no")]
    # The ring is the poster partial, out of band, outside the section (#111).
    assert f'class="film-card__poster has-trigger-icon" id="film-card-poster-{heavy.pk}" hx-swap-oob="outerHTML"' in answer
    assert answer.count("Powered by DoesTheDogDie.com") == 1


def test_unwatching_takes_the_row_the_block_and_the_ring_away(voters, heavy):
    watched.set_ticked(voters["ada"], DOG, True)
    answer = watch(signed_in(voters["ada"]), heavy, DOG, on=False, headers=HTMX).text

    assert toggles(answer) == [("dog death", DOG, 1, False), ("cat death", CAT, 1, False)]
    assert "dtdd__matched" not in answer
    assert RING not in answer and 'hx-swap-oob="outerHTML"' in answer


def test_a_thin_match_is_listed_without_the_ring(voters, vocabulary):  # noqa: F811
    thin = add(voters["Hanna"], "Thin", dog=(1, 0))
    answer = watch(signed_in(voters["ada"]), thin, DOG, headers=HTMX).text

    assert "dtdd__matched" in answer and RING not in answer


def test_the_pool_shows_the_ring_after_a_watch(voters, heavy):
    ada = signed_in(voters["ada"])
    watch(ada, heavy, DOG, headers=HTMX)

    assert ringed(ada.get("/").text, heavy)


def test_my_warnings_finds_the_topic_ticked_and_unticked_after_unwatching(voters, heavy):
    ada = signed_in(voters["ada"])

    watch(ada, heavy, DOG, headers=HTMX)
    assert f'id="topic-{DOG}" class="warnings__topic is-ticked"' in ada.get(PAGE).text
    watch(ada, heavy, DOG, on=False, headers=HTMX)
    assert "is-ticked" not in ada.get(PAGE).text


def test_a_post_in_run_writes_nothing_and_reloads_the_tab(voters, heavy):
    walk_to(Phase.RUN)
    response = watch(signed_in(voters["ada"]), heavy, DOG, headers=HTMX)

    assert response.headers["HX-Redirect"] == "/"
    assert watched.ticked_ids(voters["ada"]) == set()


def test_a_plain_post_is_answered_with_the_page(voters, heavy):
    response = watch(signed_in(voters["ada"]), heavy, DOG)

    assert response.status_code == 302 and response["Location"] == "/"
    assert watched.ticked_ids(voters["ada"]) == {DOG}


def test_the_toggles_are_absent_with_i_dont_care_on(voters, heavy):
    watched.stop_caring(voters["ada"])
    fetched = signed_in(voters["ada"]).get(f"{LIST}?suggestion={heavy.pk}", headers=HTMX).text

    assert "dtdd__watch" not in fetched and "dog death" in fetched


def test_a_stale_watch_with_i_dont_care_on_writes_nothing_and_reloads_the_tab(voters, heavy):
    watched.stop_caring(voters["ada"])
    response = watch(signed_in(voters["ada"]), heavy, DOG, headers=HTMX)

    assert response.headers["HX-Redirect"] == "/"
    assert watched.ticked_ids(voters["ada"]) == set()


def test_unwatching_with_i_dont_care_on_answers_without_toggles(voters, heavy):
    watched.stop_caring(voters["ada"])
    answer = watch(signed_in(voters["ada"]), heavy, DOG, on=False, headers=HTMX)

    assert answer.status_code == 200 and "dtdd__watch" not in answer.text


def test_the_admins_list_carries_no_toggles(admin, heavy):
    fetched = admin.get(f"/console/films/dtdd/?suggestion={heavy.pk}", headers=HTMX).text

    assert "dog death" in fetched and "dtdd__watch" not in fetched


@pytest.mark.parametrize(
    "body",
    [{"topic": "x", "ticked": "1"}, {"topic": str(DOG), "ticked": "2"}, {"topic": "0", "ticked": "1"}, {"topic": "", "ticked": ""}],
)
def test_a_malformed_post_is_refused(voters, heavy, body):
    assert signed_in(voters["ada"]).post(WATCH, {"suggestion": str(heavy.pk), **body}, headers=HTMX).status_code == 400


def test_a_card_withdrawn_since_reloads_the_tab_and_writes_nothing(voters, heavy):
    pk = heavy.pk
    heavy.delete()
    response = signed_in(voters["ada"]).post(WATCH, {"suggestion": str(pk), "topic": str(DOG), "ticked": "1"}, headers=HTMX)

    assert response.headers["HX-Redirect"] == "/" and watched.ticked_ids(voters["ada"]) == set()


def test_a_get_of_the_toggle_is_not_allowed(voters):
    assert signed_in(voters["ada"]).get(WATCH).status_code == 405


def test_each_toggle_keeps_its_id_through_the_swap_so_keyboard_focus_stays_on_it(voters, heavy):
    ada = signed_in(voters["ada"])
    fetched = ada.get(f"{LIST}?suggestion={heavy.pk}", headers=HTMX).text
    answer = watch(ada, heavy, DOG, headers=HTMX).text

    ids = lambda text: re.findall(r'<button[^>]*id="(dtdd-watch-[^"]+)"', text)  # noqa: E731
    assert ids(fetched) == [f"dtdd-watch-{heavy.pk}-{DOG}", f"dtdd-watch-{heavy.pk}-{CAT}"]
    assert ids(answer) == ids(fetched)
