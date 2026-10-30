"""A voter's own note on a film in the pool, and the pitch, saved from the opened card's phase bar (#21, #27, #88)."""

import html
import re

import pytest

from ribcage.phase.order import Phase
from ribcage.suggestions.models import Note, Suggestion
from tests.films import a_tmdb_film
from tests.http.test_phase import walk_to
from tests.http.test_phase_check import send

NOTE = "/note/"
HTMX = {"HX-Request": "true"}
WINDOW = [Phase.SUGGEST, Phase.APPROVE]
OUTSIDE_THE_WINDOW = [Phase.PICK, Phase.RUN]
PITCH = "The one with the kennel scene. Lights off."


@pytest.fixture
def the_thing(voters):
    # Hanna's suggestion, with her pitch; ada and Dani are the other voters.
    return Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing"), PITCH)


def signed_in(client, voter):
    client.force_login(voter)
    return client


@pytest.fixture
def dani(client, voters):
    return signed_in(client, voters["Dani"])


@pytest.fixture
def hanna(client, voters):
    return signed_in(client, voters["Hanna"])


def save(client, suggestion, text, headers=HTMX, **extra):
    return client.post(NOTE, {"suggestion": suggestion.pk, "text": text, **extra}, headers=headers)


def notes_on(suggestion):
    return {note.author.display_name if note.author else None: note.text for note in Note.objects.filter(suggestion=suggestion)}


def note_box(page):
    return re.search(r'<form class="note-box.*?</form>', page, re.S)[0]


def box_text(page):
    return html.unescape(re.search(r"<textarea[^>]*>(.*?)</textarea>", note_box(page), re.S)[1])


def said(page):
    return html.unescape(re.search(r'<p class="note-box__said[^"]*"[^>]*>(.*?)</p>', note_box(page), re.S)[1])


@pytest.mark.parametrize("phase", WINDOW)
def test_a_note_is_saved_in_suggest_and_approve(dani, the_thing, phase):
    walk_to(phase)

    response = save(dani, the_thing, "I'm in.")

    assert response.status_code == 200
    assert notes_on(the_thing) == {"Hanna": PITCH, "Dani": "I'm in."}


@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
def test_an_htmx_save_outside_the_window_writes_nothing_and_reloads_the_tab_onto_the_phase_page(dani, the_thing, phase):
    walk_to(phase)

    response = save(dani, the_thing, "I'm in.")

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")
    assert notes_on(the_thing) == {"Hanna": PITCH}


@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
def test_a_plain_save_outside_the_window_writes_nothing_and_is_sent_to_the_phase_page(dani, the_thing, phase):
    walk_to(phase)

    response = save(dani, the_thing, "I'm in.", headers={})

    assert (response.status_code, response.headers["Location"]) == (302, "/")
    assert notes_on(the_thing) == {"Hanna": PITCH}


def test_the_save_answers_with_the_one_card_closed_its_note_list_updated_not_the_pool(dani, voters, the_thing):
    Suggestion.objects.suggest(voters["ada"], a_tmdb_film(431, "Cube"), "Six strangers in a box.")

    page = save(dani, the_thing, "I'm in.").text

    assert page.count("<article") == 1
    assert '<article class="film-card"' in page and "is-open" not in page
    assert "Cube" not in page and "<main>" not in page
    assert re.search(r'<li class="note note--yours">.*I&#x27;m in\..*Dani</span></li>', page)
    assert (box_text(page), said(page)) == ("I'm in.", "") and "Saved." not in page


def test_a_saved_note_is_in_the_list_once_flagged_as_the_viewers_for_the_open_card_to_leave_out(dani, voters, the_thing):
    the_thing.notes.create(author=voters["ada"], text="Seen it twice.")

    page = save(dani, the_thing, "I'm in.").text

    assert page.count('class="note note--yours"') == 1
    assert 'class="note"><p class="note__text">Seen it twice.' in page


def test_a_cleared_note_leaves_the_list_and_the_box(dani, voters, the_thing):
    the_thing.notes.create(author=voters["Dani"], text="I'm in.")

    page = save(dani, the_thing, "").text

    assert "note--yours" not in page and "I&#x27;m in." not in page
    assert (box_text(page), said(page)) == ("", "") and "is-open" not in page and "Cleared." not in page


def test_the_pitch_on_the_viewers_own_card_is_flagged_as_theirs(hanna, the_thing):
    page = save(hanna, the_thing, PITCH + " More.").text

    assert 'class="note note--pitch note--yours"' in page


def test_a_plain_save_inside_the_window_writes_and_is_sent_to_the_phase_page(dani, the_thing):
    response = save(dani, the_thing, "I'm in.", headers={})

    assert (response.status_code, response.headers["Location"]) == (302, "/")
    assert notes_on(the_thing)["Dani"] == "I'm in."


def test_saving_again_edits_the_voters_one_note(dani, the_thing):
    save(dani, the_thing, "I'm in.")

    save(dani, the_thing, "  I'm in, if it's late.  ")

    assert notes_on(the_thing) == {"Hanna": PITCH, "Dani": "I'm in, if it's late."}


def test_only_its_author_edits_a_note(dani, voters, the_thing):
    the_thing.notes.create(author=voters["ada"], text="Seen it twice.")

    save(dani, the_thing, "Overwritten?", author=voters["ada"].pk, note=1)

    # A voter's save only ever reaches their own note, whatever else the post names.
    assert notes_on(the_thing) == {"Hanna": PITCH, "ada": "Seen it twice.", "Dani": "Overwritten?"}


def test_no_one_but_the_suggester_edits_the_pitch(dani, the_thing):
    save(dani, the_thing, "A different pitch.")

    assert notes_on(the_thing)["Hanna"] == PITCH


@pytest.mark.parametrize("cleared", ["", "  \r\n  "])
def test_clearing_a_note_deletes_it(dani, voters, the_thing, cleared):
    save(dani, the_thing, "I'm in.")

    page = save(dani, the_thing, cleared).text

    assert notes_on(the_thing) == {"Hanna": PITCH}
    assert "Dani</span>" not in page
    assert (box_text(page), said(page)) == ("", "") and "is-open" not in page


def test_clearing_a_note_that_was_never_written_writes_nothing(dani, the_thing):
    save(dani, the_thing, "")

    assert notes_on(the_thing) == {"Hanna": PITCH}


def test_the_suggester_edits_their_pitch(hanna, the_thing):
    save(hanna, the_thing, "Better late, lights off.")

    assert notes_on(the_thing) == {"Hanna": "Better late, lights off."}


@pytest.mark.parametrize("phase", WINDOW)
def test_a_pitch_cant_be_cleared_and_says_so_gently_with_the_pitch_back_in_the_box(hanna, the_thing, phase):
    walk_to(phase)

    page = save(hanna, the_thing, "   ").text

    assert notes_on(the_thing) == {"Hanna": PITCH}
    assert box_text(page) == PITCH
    assert said(page) == (
        "A suggestion needs its pitch, so yours is back as it was. Change it however you like."
    )


def test_a_note_over_the_cap_is_refused_whole_with_a_message_and_the_text_kept_in_the_box(dani, the_thing, settings):
    settings.NOTE_MAX_LENGTH = 20
    long_note = "This one is far too long to keep."

    page = save(dani, the_thing, long_note).text

    assert notes_on(the_thing) == {"Hanna": PITCH}
    assert box_text(page) == long_note
    assert said(page) == "That's 33 characters, and a note holds 20. Trim it a little."


def test_a_refused_note_answers_the_card_open_with_save_enabled_and_the_saved_words_named(dani, voters, the_thing, settings):
    settings.NOTE_MAX_LENGTH = 20
    the_thing.notes.create(author=voters["Dani"], text="I'm in.")

    page = save(dani, the_thing, "This one is far too long to keep.").text

    assert '<article class="film-card is-open"' in page
    assert "data-save-waits data-unsaved" in page and 'data-saved="I&#x27;m in."' in page and "disabled" not in page


def test_a_freshly_opened_card_waits_for_a_change_by_script_and_its_save_is_enabled_without_it(dani, voters, the_thing):
    the_thing.notes.create(author=voters["Dani"], text="I'm in.")

    page = note_box(dani.get("/").text)

    # Script disables Save until the box differs from `data-saved`; the markup is enabled, so a post without script works (#132).
    assert "data-save-waits" in page and "data-unsaved" not in page and 'data-saved="I&#x27;m in."' in page
    assert re.search(r'<button type="submit">Save</button>', page)


def test_a_pitch_over_the_cap_is_refused_and_the_old_pitch_kept(hanna, the_thing, settings):
    settings.NOTE_MAX_LENGTH = 20

    page = save(hanna, the_thing, "A pitch that runs well past the cap.").text

    assert notes_on(the_thing) == {"Hanna": PITCH}
    assert said(page) == "That's 36 characters, and a pitch holds 20. Trim it a little."


def test_a_note_at_the_cap_is_kept_whole(dani, the_thing, settings):
    settings.NOTE_MAX_LENGTH = 20

    save(dani, the_thing, "x" * 20)

    assert notes_on(the_thing)["Dani"] == "x" * 20


@pytest.mark.parametrize("method", ["options", "trace", "put", "patch", "delete"])
@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.VOTE])
def test_the_note_route_answers_every_method_but_get_head_and_post_with_405(dani, the_thing, method, phase):
    walk_to(phase)

    response = send(dani, method, NOTE, f"suggestion={the_thing.pk}&text=Hijacked")

    assert response.status_code == 405
    assert notes_on(the_thing) == {"Hanna": PITCH}


def test_the_note_route_is_no_page(dani):
    assert dani.get(NOTE).status_code == 405


@pytest.mark.parametrize("named", [None, "999", "not-a-number"])
def test_a_save_for_a_suggestion_that_is_gone_writes_nothing_and_reloads_the_tab(dani, the_thing, named):
    fields = {"text": "I'm in."} | ({} if named is None else {"suggestion": named})

    response = dani.post(NOTE, fields, headers=HTMX)

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")
    assert Note.objects.count() == 1


@pytest.mark.parametrize(("phase", "bar"), [(Phase.SUGGEST, "phase-bar--suggest"), (Phase.APPROVE, "phase-bar--approve")])
def test_each_card_in_the_pool_carries_the_phases_bar_with_the_viewers_own_note(dani, voters, the_thing, phase, bar):
    the_thing.notes.create(author=voters["Dani"], text="I'm in.")
    walk_to(phase)

    page = dani.get("/").text

    assert f'class="phase-bar {bar}"' in page
    assert f'name="suggestion" value="{the_thing.pk}"' in page
    assert box_text(page) == "I'm in."
    assert "Your note" in note_box(page)


def test_on_the_voters_own_suggestion_the_box_is_their_pitch(hanna, the_thing):
    page = hanna.get("/").text

    assert box_text(page) == PITCH
    assert "Your pitch" in note_box(page)


def test_a_save_in_approve_answers_with_approves_bar(dani, the_thing):
    walk_to(Phase.APPROVE)

    assert 'class="phase-bar phase-bar--approve"' in save(dani, the_thing, "I'm in.").text


def test_a_saved_note_swaps_in_a_card_marked_mine_for_its_suggester_only(client, voters, the_thing):
    assert " data-mine>" in save(signed_in(client, voters["Hanna"]), the_thing, "Still the pitch.").text
    assert " data-mine" not in save(signed_in(client, voters["Dani"]), the_thing, "A note.").text
