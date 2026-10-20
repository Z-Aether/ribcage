import dataclasses

import pytest
from django.template.loader import render_to_string

from ribcage.films import corpus
from ribcage.films.card import ELLIPSIS, FilmCard, Note, trimmed
from ribcage.films.film import Film, RuntimeSource, hand_entered
from ribcage.films.poster import TITLE_CARD_FILLS, poster_url, title_card_fill

THE_SHINING = Film(
    tmdb_id=694,
    title="The Shining",
    original_title="The Shining",
    year=1980,
    directors=("Stanley Kubrick",),
    certificate="R",
    trailer_key="S014oGZiSdI",
    runtime=144,
    runtime_source=RuntimeSource.TMDB,
    poster_path="/uAR0AWqhQL1hQa69UDEbb2rE5Wx.jpg",
    imdb_id="tt0081505",
)
LONG_NOTE = (
    "One of the few films that frightened all of us at once, and the hedge maze "
    "scene is better on a big screen than anything else on this list."
)


def a_card(film=THE_SHINING, **changes):
    card = FilmCard(film=film, suggester="Ada", suggester_removed=False, pitch="Watch it late.", notes=())
    return dataclasses.replace(card, **changes)


def render(card, expanded=False):
    return render_to_string("components/film_card.html", {"card": card, "expanded": expanded})


def test_a_note_within_the_trim_length_is_left_whole():
    assert trimmed("I'm in.", 120) == "I'm in."


def test_a_long_note_is_cut_at_a_word_and_marked_with_an_ellipsis():
    short = trimmed(LONG_NOTE, 60)

    assert short == "One of the few films that frightened all of us at once, and" + ELLIPSIS
    assert len(short) <= 61


def test_a_note_with_no_word_break_near_the_length_is_cut_at_the_length():
    assert trimmed("a" * 200, 120) == "a" * 120 + ELLIPSIS


def test_a_poster_comes_from_tmdbs_keyless_image_cdn_at_the_size_asked_for():
    assert poster_url(THE_SHINING, "card") == "https://image.tmdb.org/t/p/w342/uAR0AWqhQL1hQa69UDEbb2rE5Wx.jpg"


def test_the_title_card_fill_is_a_stable_pure_function_of_the_film():
    # Pinned, so a salted hash() or a changed derivation fails here.
    assert title_card_fill(THE_SHINING) == 3
    assert title_card_fill(dataclasses.replace(THE_SHINING, poster_path=None, title="Retitled")) == 3
    assert title_card_fill(hand_entered("Del Toro's Cabinet of Curiosities", 2022, 47)) == 5


def test_hand_entered_films_take_their_fill_from_title_and_year():
    assert title_card_fill(hand_entered("Home video", 2019, 30)) != title_card_fill(hand_entered("Home video", 2020, 30))


def test_neighbouring_films_in_the_corpus_take_different_fills():
    fills = [title_card_fill(recorded.film) for recorded in corpus.read_corpus()]
    shared_with_neighbour = sum(left == right for left, right in zip(fills, fills[1:]))

    assert set(fills) == set(range(TITLE_CARD_FILLS))
    # A pure function of one film makes neighbours share a fill only by chance, 1 in TITLE_CARD_FILLS (#38).
    assert shared_with_neighbour <= len(fills) // TITLE_CARD_FILLS


def test_a_posterless_film_shows_its_title_card_with_title_year_and_fill():
    film = hand_entered("Del Toro's Cabinet of Curiosities", 2022, 47)

    page = render_to_string("components/poster.html", {"film": film, "size": "tile"})

    assert 'data-fill="5"' in page
    assert "Del Toro&#x27;s Cabinet of Curiosities" in page
    assert '<span class="title-card__year">2022</span>' in page
    assert "<img" not in page


def test_a_film_with_a_poster_shows_it():
    page = render_to_string("components/poster.html", {"film": THE_SHINING, "size": "thumb"})

    assert 'src="https://image.tmdb.org/t/p/w92/uAR0AWqhQL1hQa69UDEbb2rE5Wx.jpg"' in page
    assert "title-card" not in page


def test_the_card_carries_each_note_trimmed_and_whole_with_the_pitch_first(settings):
    settings.NOTE_TRIM_LENGTH = 60
    card = a_card(pitch=LONG_NOTE, notes=(Note("Bo", "Count me in."),))

    page = render(card)

    assert page.index("note--pitch") < page.index("Count me in.")
    assert f'<span class="note__trimmed">{trimmed(LONG_NOTE, 60)}</span>' in page
    assert f'<span class="note__full">{LONG_NOTE}</span>' in page


def test_the_trim_length_comes_from_the_judgement_constant(settings):
    settings.NOTE_TRIM_LENGTH = 500

    assert "note__trimmed" not in render(a_card(pitch=LONG_NOTE))


def test_the_original_title_is_carried_only_when_it_differs():
    differing = dataclasses.replace(THE_SHINING, title="Infested", original_title="Vermines")

    assert "Vermines" in render(a_card(differing))
    assert "film-card__original" not in render(a_card())


def test_a_removed_suggester_shows_as_removed():
    page = render(a_card(suggester="Ivo", suggester_removed=True))

    assert "is-removed" in page
    assert '<span class="removed-tag">removed</span>' in page


def test_a_hand_entered_film_shows_its_runtime_as_hand_entered_and_no_tmdb_links():
    page = render(a_card(hand_entered("Del Toro's Cabinet of Curiosities", 2022, 47)))

    assert '<span class="runtime__value">47</span>' in page
    assert "by hand" in page
    assert "themoviedb.org" not in page
    assert "youtube.com" not in page


def test_a_tmdb_film_links_its_trailer_and_tmdb_page():
    page = render(a_card())

    assert "https://www.youtube.com/watch?v=S014oGZiSdI" in page
    assert "https://www.themoviedb.org/movie/694" in page
    assert '<span class="runtime__source">TMDB</span>' in page


def test_the_phase_bar_slot_is_empty_until_a_surface_fills_it():
    assert '<div class="film-card__phase-bar" data-phase-bar></div>' in render(a_card())


@pytest.mark.parametrize("expanded", [False, True])
def test_the_card_says_whether_it_is_open(expanded):
    page = render(a_card(), expanded=expanded)

    assert ("film-card is-open" in page) is expanded
    assert f'aria-expanded="{str(expanded).lower()}"' in page
