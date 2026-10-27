"""The count on the ring: the matched topics a film carries, wherever the ring shows and nowhere else (#111, #117)."""

import re

from django.conf import settings
from django.template.loader import render_to_string

from ribcage.films.card import Matched, TopicRow
from ribcage.phase.order import Phase
from ribcage.triggers import watched
from tests.http.test_card_watch import WATCH, watch
from tests.http.test_matched_topics import NOTE, add, card, pool, signed_in  # noqa: F401
from tests.http.test_my_warnings import CAT, DOG, HTMX, dtdd, vocabulary  # noqa: F401
from tests.http.test_phase import walk_to

COUNT = re.compile(r'<span class="trigger-count" role="img" aria-label="(\d+) of your warnings">(\d+)</span>')


def counts(text):
    return [(int(label), int(shown)) for label, shown in COUNT.findall(text)]


def test_a_ringed_cards_count_holds_the_number_of_matched_rows_and_an_unringed_card_has_none(voters, pool):
    assert counts(card(signed_in(voters["ada"]).get("/").text, pool["heavy"])) == [(1, 1)]
    watched.set_ticked(voters["ada"], CAT, True)
    both = add(voters["Hanna"], "Both", dog=(12, 1), cat=(8, 0))
    page = signed_in(voters["ada"]).get("/").text

    # Heavy's cat row (2 yes) is listed but thin, so it is not counted (#117).
    assert counts(card(page, pool["heavy"])) == [(1, 1)]
    assert counts(card(page, pool["thin"])) == []
    assert counts(card(page, both)) == [(2, 2)]


def test_the_count_leaves_out_thin_rows_the_block_lists_and_counts_every_strong_one(voters, pool):
    watched.set_ticked(voters["ada"], CAT, True)
    mixed = add(voters["Hanna"], "Mixed", dog=(12, 1), cat=(1, 35))
    strong = add(voters["Hanna"], "Strong", dog=(12, 1), cat=(9, 2))
    page = signed_in(voters["ada"]).get("/").text

    assert counts(card(page, mixed)) == [(1, 1)]
    assert "1 yes / 35 no" in card(page, mixed)
    assert counts(card(page, strong)) == [(2, 2)]


def test_the_dtdd_links_keep_the_standard_colour_and_only_the_on_your_list_label_is_lime():
    css = (settings.BASE_DIR / "ribcage/static/theme/theme.css").read_text(encoding="utf-8")
    lime = css[css.index("/* Lime is the trigger warnings"):]
    lime = lime[: lime.index("}")]

    assert ".dtdd a" not in lime
    assert "[data-skin] .dtdd__matched .dtdd__group" in lime
    assert "On your list" in render_to_string("components/dtdd_matched.html", {"matched": Matched((TopicRow("dogs dying", 3, 1),), strong=0)})


def test_the_count_sits_inside_the_posters_wrapper_beside_the_ring(voters, pool):
    page = signed_in(voters["ada"]).get("/").text

    wrapper = re.search(r'<div class="film-card__poster has-trigger-icon"[^>]*>.*?</div>', card(page, pool["heavy"]), re.S)[0]
    assert counts(wrapper) == [(1, 1)]


def test_a_thin_match_is_listed_without_the_ring_and_so_without_the_count(voters, pool):
    page = signed_in(voters["ada"]).get("/").text

    assert "dtdd__matched" in card(page, pool["thin"]) and counts(card(page, pool["thin"])) == []


def test_a_watch_toggles_swap_carries_the_count_and_its_count_follows_each_toggle(voters, vocabulary):  # noqa: F811
    film = add(voters["Hanna"], "Heavy", dog=(12, 1), cat=(2, 0))
    ada = signed_in(voters["ada"])

    first = watch(ada, film, DOG, headers=HTMX).text
    assert counts(poster_swap(first)) == [(1, 1)]
    second = watch(ada, film, CAT, headers=HTMX).text
    assert counts(poster_swap(second)) == [(1, 1)]
    # The count is no part of the section, which the answer swaps in place.
    assert counts(first.split('hx-swap-oob="outerHTML"')[0]) == []
    gone = watch(ada, film, DOG, on=False, headers=HTMX).text
    # Cat alone is a thin match: listed, but no ring, so no count (#111).
    assert counts(poster_swap(gone)) == []


def poster_swap(answer):
    return re.search(r'<div class="film-card__poster[^>]*hx-swap-oob="outerHTML".*?</div>', answer, re.S)[0]


def test_a_card_a_note_swaps_in_keeps_its_count(voters, pool):
    walk_to(Phase.SUGGEST)
    page = signed_in(voters["ada"]).post(NOTE, {"suggestion": pool["heavy"].pk, "text": "Sounds great"}, headers=HTMX).text

    assert counts(page) == [(1, 1)]


def test_no_count_for_a_voter_with_nothing_ticked_or_who_does_not_care_or_on_the_admins_card(voters, pool, admin):
    assert counts(signed_in(voters["Hanna"]).get("/").text) == []
    watched.stop_caring(voters["ada"])
    assert counts(signed_in(voters["ada"]).get("/").text) == []
    assert counts(admin.get("/console/films/").text) == []
    assert WATCH


def test_the_lime_words_mark_the_warnings_page_how_it_works_and_the_menu(voters, vocabulary):  # noqa: F811
    ada = signed_in(voters["ada"])

    assert '<span class="trigger-words">will be marked for you</span>' in ada.get("/warnings/").text
    assert '<span class="trigger-words">marked for you alone</span>' in ada.get("/how-it-works/").text
    assert '<a class="trigger-words" href="/warnings/">My warnings</a>' in ada.get("/").text


def test_the_nag_bars_link_is_a_lime_word_by_the_class_not_by_its_own_rule(voters):
    page = signed_in(voters["Hanna"]).get("/").text

    assert '<a class="trigger-words" href="/warnings/">Set up my warnings</a>' in page


def test_the_gallery_shows_the_count_on_a_tile_and_a_title_card_tile(voters, settings):
    settings.DEBUG = True
    page = signed_in(voters["ada"]).get("/gallery/").text

    assert counts(page).count((1, 1)) >= 1 and (3, 3) in counts(page)
    assert 'class="trigger-words"' in page
