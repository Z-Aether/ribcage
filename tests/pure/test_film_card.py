import dataclasses
import re

import pytest
from django.template.loader import render_to_string

from ribcage.films.card import ELLIPSIS, FilmCard, Note, NoteBox, RuntimePencil, trimmed
from ribcage.films.film import Film, RuntimeSource, hand_entered
from ribcage.films.poster import poster_url

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


def test_a_posterless_film_shows_its_title_card_with_the_title_and_year_beneath():
    film = hand_entered("Del Toro's Cabinet of Curiosities", 2022, 47)

    page = render_to_string("components/poster.html", {"film": film, "size": "tile"})

    assert '<span class="title-card__title">Del Toro&#x27;s Cabinet of Curiosities</span>' in page
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


# The runtime pencil (#90)


def runtime_line(page):
    return re.search(r'<div class="film-card__runtime[^"]*" data-runtime>.*?</div>', page, re.S)[0]


def test_the_runtime_line_offers_no_pencil_unless_the_card_carries_one():
    assert "runtime__pencil" not in render(a_card(suggestion_id=7))


def test_the_pencil_ends_the_runtime_line_and_opens_it_in_place():
    line = runtime_line(render(a_card(suggestion_id=7, runtime_pencil=RuntimePencil())))

    pencil = re.search(r'<a class="runtime__pencil"[^>]*>', line)[0]
    assert 'hx-get="/runtime/?suggestion=7"' in pencil
    assert 'hx-target="closest [data-runtime]"' in pencil
    assert 'aria-label="Correct the runtime"' in pencil
    assert line.index("runtime__source") < line.index("runtime__pencil")


def test_the_open_pencil_edits_the_current_runtime():
    line = runtime_line(render(a_card(suggestion_id=7, runtime_pencil=RuntimePencil(open=True))))

    assert re.search(r'<input [^>]*name="runtime"[^>]*value="144"', line)
    assert "runtime__refusal" not in line


def test_the_runtime_line_renders_no_save_and_no_cancel():
    line = runtime_line(render(a_card(suggestion_id=7, runtime_pencil=RuntimePencil(open=True, typed="2h 31", refusal="No."))))

    assert not re.search(r"<button|<form|Save|Cancel|cancel", line)


def test_the_open_box_joins_the_note_boxs_form_and_counts_as_a_change():
    card = a_card(suggestion_id=7, note_box=NoteBox(text="", is_pitch=False), runtime_pencil=RuntimePencil(open=True))
    page = render_to_string("components/film_card.html", {"card": card, "expanded": True, "phase_bar": "components/suggest_bar.html"})

    assert re.search(r'<input [^>]*name="runtime"[^>]*form="note-7"[^>]*data-counts-as-change', runtime_line(page))
    assert '<form class="note-box" id="note-7"' in page


def test_a_card_with_no_note_box_leaves_the_runtime_box_joined_to_no_form():
    line = runtime_line(render(a_card(suggestion_id=7, runtime_pencil=RuntimePencil(open=True))))

    assert " form=" not in line


def test_a_refused_runtime_stays_as_typed_beside_the_refusal():
    pencil = RuntimePencil(open=True, typed="2h 31", refusal="A runtime is whole minutes, like 144.")

    line = runtime_line(render(a_card(suggestion_id=7, runtime_pencil=pencil)))

    assert re.search(r'<input [^>]*name="runtime"[^>]*value="2h 31"', line)
    assert '<p class="runtime__refusal" role="status">A runtime is whole minutes, like 144.</p>' in line


def test_the_open_line_still_reads_the_runtime_it_holds_for_a_card_closed_over_the_box():
    line = runtime_line(render(a_card(suggestion_id=7, runtime_pencil=RuntimePencil(open=True))))

    assert line.index("runtime__read") < line.index("runtime__edit")
    assert '<span class="runtime__value">144</span>' in line


def test_a_card_closed_over_an_open_box_keeps_its_pencil_and_the_box_alone_has_the_id():
    page = render(a_card(suggestion_id=7, runtime_pencil=RuntimePencil(open=True, typed="150")), expanded=False)
    line = runtime_line(page)

    pencil = re.search(r'<a class="runtime__pencil"[^>]*>', line)[0]
    assert 'hx-get="/runtime/?suggestion=7"' in pencil
    assert "id=" not in pencil and line.count('id="runtime-7"') == 1
    assert re.search(r'<input [^>]*id="runtime-7"[^>]*name="runtime"', line)
    assert line.index("runtime__pencil") < line.index("runtime__edit")


def test_the_open_box_names_the_stored_runtime_whatever_is_typed_in_it():
    line = runtime_line(render(a_card(suggestion_id=7, runtime_pencil=RuntimePencil(open=True, typed="150"))))

    assert re.search(r'<input [^>]*name="runtime"[^>]*data-stored="144"[^>]*value="150"', line)


def test_the_open_box_of_a_film_with_no_runtime_names_none_stored():
    line = runtime_line(render(a_card(film=dataclasses.replace(THE_SHINING, runtime=None), suggestion_id=7, runtime_pencil=RuntimePencil(open=True))))

    assert 'data-stored=""' in line
