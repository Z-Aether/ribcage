"""The runtime pencil: any voter correcting a film's runtime for the copy the group will watch, in SUGGEST,
on a film nothing downstream holds, inline on the card's runtime line; the note box's one Save takes the runtime with the note (#21, #27, #34, #90, #133)."""

import html
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.ballot.models import BallotRecord
from ribcage.phase.order import Phase
from ribcage.suggestions import notes, runtime, saving, withdrawal
from ribcage.suggestions.models import Approval, Note, Suggestion
from ribcage.suggestions.views import open_runtime
from tests.films import CABINET_OF_CURIOSITIES, a_tmdb_film
from tests.http.test_phase import walk_to
from tests.http.test_phase_check import send

RUNTIME = "/runtime/"
NOTE = "/note/"
HTMX = {"HX-Request": "true"}
OUTSIDE_THE_WINDOW = [Phase.APPROVE, Phase.VOTE, Phase.PICK, Phase.RUN]
PITCH = "Lights off."


@pytest.fixture
def the_thing(voters):
    # Hanna's suggestion, as TMDB gave it: 109 minutes.
    return Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing", runtime=109), PITCH)


@pytest.fixture
def cube(voters):
    return Suggestion.objects.suggest(voters["Dani"], a_tmdb_film(431, "Cube", runtime=90), "Six strangers in a box.")


def signed_in(client, voter):
    client.force_login(voter)
    return client


@pytest.fixture
def hanna(client, voters):
    return signed_in(client, voters["Hanna"])


@pytest.fixture
def dani(client, voters):
    return signed_in(client, voters["Dani"])


def correct(client, suggestion, typed, text="", headers=HTMX):
    """The card's one Save, posted with the runtime box open: the note box's text and the runtime together (#133)."""
    named = suggestion if isinstance(suggestion, str) else suggestion.pk
    return client.post(NOTE, {"suggestion": named, "text": text, "runtime": typed}, headers=headers)


def open_pencil(client, suggestion, headers=HTMX, **extra):
    return client.get(RUNTIME, {"suggestion": suggestion.pk, **extra}, headers=headers)


def notes_on(suggestion):
    return {note.author.display_name: note.text for note in Note.objects.filter(suggestion=suggestion)}


def runtimes(suggestion):
    suggestion.refresh_from_db()
    return suggestion.runtime, suggestion.tmdb_runtime


def approve(suggestion):
    Suggestion.objects.filter(pk=suggestion.pk).update(approval=Approval.APPROVED)


def text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def runtime_line(page):
    return re.search(r'<div class="film-card__runtime[^"]*" data-runtime>.*?</div>', page, re.S)[0]


def box_text(page):
    return html.unescape(re.search(r"<textarea[^>]*>(.*?)</textarea>", page, re.S)[1])


def noted(page):
    """What the note box says beside itself: its refusal, or nothing."""
    return html.unescape(re.search(r'<p class="note-box__said[^"]*"[^>]*>(.*?)</p>', page, re.S)[1])


def typed_in(line):
    return html.unescape(re.search(r'<input [^>]*name="runtime"[^>]*value="([^"]*)"', line)[1])


def refusal(line):
    found = re.search(r'<p class="runtime__refusal" role="status">(.*?)</p>', line, re.S)
    return html.unescape(found[1]) if found else None


def pencils_on(page):
    """The suggestion of each card in the page whose runtime line carries the pencil."""
    cards = re.findall(r'<article class="film-card[^"]*" data-film-card data-suggestion="(\d+)"[^>]*>(.*?)</article>', page, re.S)
    return [int(pk) for pk, shown in cards if "runtime__pencil" in runtime_line(shown)]


def test_the_pencils_route_only_reads_so_it_has_no_window_and_no_post():
    assert not hasattr(open_runtime, "phase_window")


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.VOTE])
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete", "options"])
def test_the_runtime_route_answers_everything_but_get_and_head_with_405(dani, the_thing, method, phase):
    walk_to(phase)

    response = send(dani, method, RUNTIME, f"suggestion={the_thing.pk}&runtime=127")

    assert (response.status_code, response.headers["Allow"]) == (405, "GET, HEAD")
    assert runtimes(the_thing) == (109, 109)


# The one Save


@pytest.mark.parametrize("voter", ["hanna", "dani"], ids=["the suggester", "another voter"])
def test_one_post_carrying_a_note_and_a_runtime_saves_both(request, the_thing, voter):
    client = request.getfixturevalue(voter)

    response = correct(client, the_thing, "127", "A new line.")

    assert response.status_code == 200
    assert runtimes(the_thing) == (127, 109)
    assert notes_on(the_thing)["Hanna" if voter == "hanna" else "Dani"] == "A new line."


def test_the_answer_is_the_card_closed_showing_the_runtime_by_hand_and_the_note(dani, the_thing):
    page = correct(dani, the_thing, "127", "I'm in.").text

    assert page.count("<article") == 1 and "is-open" not in page
    line = runtime_line(page)
    assert text(line) == "127 min by hand ✎" and "<input" not in line
    assert re.search(r'<li class="note note--yours">.*I&#x27;m in\..*Dani</span></li>', page)
    assert 'name="runtime"' not in page


def test_a_correction_back_to_tmdbs_runtime_reads_as_tmdbs_again(dani, the_thing):
    correct(dani, the_thing, "127", "I'm in.")

    page = correct(dani, the_thing, "109", "I'm in.").text

    assert text(runtime_line(page)) == "109 min TMDB ✎"
    assert runtimes(the_thing) == (109, 109)


def test_tmdbs_runtime_is_kept_unchanged(dani, the_thing):
    correct(dani, the_thing, "127")
    correct(dani, the_thing, "140")

    assert Suggestion.objects.get(pk=the_thing.pk).tmdb_runtime == 109


def test_a_hand_entered_films_runtime_is_corrected_and_still_has_no_tmdb_runtime(dani, voters):
    cabinet = Suggestion.objects.suggest(voters["Hanna"], CABINET_OF_CURIOSITIES, "Just the one episode.")

    correct(dani, cabinet, "52")

    assert runtimes(cabinet) == (52, None)


def test_a_dropped_film_nothing_holds_can_be_corrected(dani, the_thing):
    Suggestion.objects.filter(pk=the_thing.pk).update(approval=Approval.DROPPED)

    correct(dani, the_thing, "127")

    assert runtimes(the_thing) == (127, 109)


def test_a_correction_touches_only_its_own_film(dani, the_thing, cube):
    correct(dani, the_thing, "127")

    assert runtimes(cube) == (90, 90)


def test_with_the_runtime_box_shut_the_save_writes_the_note_alone(dani, the_thing):
    response = dani.post(NOTE, {"suggestion": the_thing.pk, "text": "I'm in."}, headers=HTMX)

    assert response.status_code == 200
    assert runtimes(the_thing) == (109, 109)
    assert notes_on(the_thing)["Dani"] == "I'm in."


def test_a_plain_save_with_the_box_open_writes_both_and_is_sent_to_the_phase_page(dani, the_thing):
    response = correct(dani, the_thing, "127", "I'm in.", headers={})

    assert (response.status_code, response.headers["Location"]) == (302, "/")
    assert runtimes(the_thing) == (127, 109)
    assert notes_on(the_thing)["Dani"] == "I'm in."


@pytest.mark.parametrize(
    ("typed", "said"),
    [
        ("0", runtime.NOT_POSITIVE),
        ("-20", runtime.NOT_POSITIVE),
        ("", runtime.EMPTY),
        ("127.5", runtime.NOT_WHOLE_MINUTES),
        ("2h 7", runtime.NOT_WHOLE_MINUTES),
        ("100000", runtime.TOO_LONG),
    ],
)
def test_a_refused_runtime_with_a_good_note_saves_neither_and_answers_the_open_card_with_both_typings(dani, the_thing, typed, said):
    response = correct(dani, the_thing, typed, "I'm in.")

    assert response.status_code == 200
    assert runtimes(the_thing) == (109, 109)
    assert notes_on(the_thing) == {"Hanna": PITCH}
    page = response.text
    assert page.count("<article") == 1 and 'class="film-card is-open"' in page
    line = runtime_line(page)
    assert (typed_in(line), refusal(line)) == (typed, said)
    assert (box_text(page), noted(page)) == ("I'm in.", "")


def test_a_refused_note_with_a_good_runtime_saves_neither_and_answers_the_open_card_with_both_typings(dani, the_thing, settings):
    settings.NOTE_MAX_LENGTH = 20
    long = "x" * 21

    page = correct(dani, the_thing, "127", long).text

    assert runtimes(the_thing) == (109, 109)
    assert notes_on(the_thing) == {"Hanna": PITCH}
    assert 'class="film-card is-open"' in page
    line = runtime_line(page)
    assert (typed_in(line), refusal(line)) == ("127", None)
    assert box_text(page) == long
    assert noted(page) == notes.too_long(notes.TooLong(21, 20), False)


def test_a_pitch_emptied_with_a_good_runtime_is_put_back_and_saves_neither(hanna, the_thing):
    page = correct(hanna, the_thing, "127", "").text

    assert runtimes(the_thing) == (109, 109)
    assert notes_on(the_thing) == {"Hanna": PITCH}
    assert 'class="film-card is-open"' in page
    assert (box_text(page), noted(page)) == (PITCH, notes.PITCH_REQUIRED)
    assert typed_in(runtime_line(page)) == "127" and refusal(runtime_line(page)) is None


def test_a_refused_note_and_a_refused_runtime_each_show_beside_their_own_box(dani, the_thing, settings):
    settings.NOTE_MAX_LENGTH = 20

    page = correct(dani, the_thing, "abc", "x" * 21).text

    assert runtimes(the_thing) == (109, 109)
    assert refusal(runtime_line(page)) == runtime.NOT_WHOLE_MINUTES
    assert noted(page) == notes.too_long(notes.TooLong(21, 20), False)


def test_the_refused_card_keeps_save_enabled_by_marking_the_open_box_a_change(dani, the_thing):
    page = correct(dani, the_thing, "0", "").text

    assert re.search(r'<input [^>]*name="runtime"[^>]*data-counts-as-change', page)
    assert not re.search(r'<button type="submit"[^>]*disabled', page)


def loaded(suggestion):
    return withdrawal.with_holds(Suggestion.objects.filter(pk=suggestion.pk)).get()


def test_saving_is_one_transaction_of_its_own_whoever_calls_it(voters, the_thing, monkeypatch):
    # Called outside any view's phase window, so only `saving.save`'s own transaction can take the note back (#133).
    def fails(suggestion, typed):
        raise RuntimeError("the database went away")

    monkeypatch.setattr(runtime, "correct", fails)

    with pytest.raises(RuntimeError):
        saving.save(loaded(the_thing), voters["Dani"], "I'm in.", "127", Phase.SUGGEST)

    assert notes_on(the_thing) == {"Hanna": PITCH}


def test_a_refused_note_posted_with_the_box_shut_opens_no_runtime_box(dani, the_thing, settings):
    settings.NOTE_MAX_LENGTH = 20

    page = dani.post(NOTE, {"suggestion": the_thing.pk, "text": "x" * 21}, headers=HTMX).text

    assert noted(page) == notes.too_long(notes.TooLong(21, 20), False)
    assert 'name="runtime"' not in page and "runtime__edit" not in page
    assert "runtime__pencil" in runtime_line(page)


def test_a_failure_in_the_second_write_takes_the_first_back(dani, the_thing, monkeypatch):
    # Both writes are one transaction (#133).
    def fails(suggestion, typed):
        raise RuntimeError("the database went away")

    monkeypatch.setattr(runtime, "correct", fails)

    with pytest.raises(RuntimeError):
        correct(dani, the_thing, "127", "I'm in.")

    assert notes_on(the_thing) == {"Hanna": PITCH}


def test_an_approved_film_drops_the_runtime_without_a_word_and_saves_the_note(dani, the_thing):
    approve(the_thing)

    response = correct(dani, the_thing, "127", "I'm in.")

    assert runtimes(the_thing) == (109, 109)
    assert notes_on(the_thing)["Dani"] == "I'm in."
    page = response.text
    assert "is-open" not in page and "runtime__pencil" not in page and "runtime__refusal" not in page
    # The pencil leaves the line, with no explanation (#27).
    assert text(runtime_line(page)) == "109 min TMDB"


def test_a_film_held_by_a_ballot_record_since_drops_the_runtime_and_saves_the_note(dani, voters, the_thing):
    BallotRecord.objects.create(voter=voters["ada"], suggestion=the_thing, score=2)

    response = correct(dani, the_thing, "127", "I'm in.")

    assert runtimes(the_thing) == (109, 109)
    assert notes_on(the_thing)["Dani"] == "I'm in."
    assert "runtime__pencil" not in response.text


def test_a_refused_note_on_a_film_approved_since_keeps_no_runtime_box(dani, the_thing, settings):
    settings.NOTE_MAX_LENGTH = 20
    approve(the_thing)

    page = correct(dani, the_thing, "abc", "x" * 21).text

    assert 'name="runtime"' not in page and "runtime__refusal" not in page
    assert noted(page)


def test_in_approve_a_post_carrying_a_runtime_changes_no_runtime_and_saves_the_note(dani, the_thing):
    walk_to(Phase.APPROVE)

    response = correct(dani, the_thing, "127", "I'm in.")

    assert response.status_code == 200
    assert runtimes(the_thing) == (109, 109)
    assert notes_on(the_thing)["Dani"] == "I'm in."
    assert "runtime__refusal" not in response.text and 'name="runtime"' not in response.text


@pytest.mark.parametrize("phase", [Phase.VOTE, Phase.PICK, Phase.RUN])
def test_a_save_carrying_a_runtime_outside_the_window_writes_nothing_and_reloads_the_tab(dani, the_thing, phase):
    walk_to(phase)

    response = correct(dani, the_thing, "127", "I'm in.")

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")
    assert runtimes(the_thing) == (109, 109)
    assert notes_on(the_thing) == {"Hanna": PITCH}


@pytest.mark.parametrize("named", ["999", "not-a-number", ""])
def test_a_save_naming_no_suggestion_writes_nothing_and_reloads_the_tab(dani, the_thing, named):
    response = correct(dani, named, "127", "I'm in.")

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")
    assert runtimes(the_thing) == (109, 109)


# Opening the pencil


def test_opening_the_pencil_writes_nothing(dani, the_thing):
    with CaptureQueriesContext(connection) as captured:
        response = open_pencil(dani, the_thing)

    assert response.status_code == 200
    assert [query["sql"] for query in captured if not query["sql"].lstrip().upper().startswith("SELECT")] == []


def test_the_open_pencil_edits_the_current_runtime_on_its_line(dani, the_thing):
    line = runtime_line(open_pencil(dani, the_thing).text)

    assert typed_in(line) == "109"
    assert refusal(line) is None


def test_the_open_box_has_no_save_or_cancel_and_joins_the_note_boxs_form(dani, the_thing):
    page = open_pencil(dani, the_thing).text
    line = runtime_line(page)

    assert "<button" not in line and "<form" not in line and "Cancel" not in line and "Save" not in line
    assert re.search(rf'<input [^>]*name="runtime"[^>]*form="note-{the_thing.pk}"', line)
    assert 'data-counts-as-change' in line


def test_the_card_draws_the_note_form_the_box_joins_and_the_one_save_beside_it(dani, the_thing):
    page = dani.get("/").text

    assert f'<form class="note-box" id="note-{the_thing.pk}"' in page
    assert page.count(">Save</button>") == 1
    assert "Cancel" not in runtime_line(page)


def test_the_pencils_address_has_no_cancel(dani, the_thing):
    assert "cancel" not in runtime_line(dani.get("/").text)


def test_the_pencil_and_its_box_share_an_id_so_focus_moves_between_them_and_never_both_at_once(dani, the_thing):
    closed = runtime_line(dani.get("/").text)
    opened = runtime_line(open_pencil(dani, the_thing).text)

    focus = f'id="runtime-{the_thing.pk}"'
    assert re.search(rf'<a class="runtime__pencil"[^>]*{focus}', closed)
    assert re.search(rf'<input [^>]*{focus}[^>]*name="runtime"', opened)
    assert opened.count(focus) == 1


def test_the_open_box_keeps_the_stored_runtime_in_the_line_for_a_card_closed_over_it(dani, the_thing):
    line = runtime_line(open_pencil(dani, the_thing).text)

    assert re.search(r'<span class="runtime__read"><span class="runtime__value">109</span>', line)


@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
def test_opening_the_pencil_outside_suggest_reloads_the_tab(dani, the_thing, phase):
    walk_to(phase)

    response = open_pencil(dani, the_thing)

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")


def test_opening_the_pencil_on_an_approved_film_shows_its_line_with_no_pencil(dani, the_thing):
    approve(the_thing)

    line = runtime_line(open_pencil(dani, the_thing).text)

    assert text(line) == "109 min TMDB"


def test_opening_the_pencil_on_a_film_withdrawn_since_reloads_the_tab(dani, the_thing):
    Suggestion.objects.filter(pk=the_thing.pk).delete()

    response = open_pencil(dani, the_thing)

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")


def test_a_plain_open_is_sent_to_the_phase_page(dani, the_thing):
    response = open_pencil(dani, the_thing, headers={})

    assert (response.status_code, response.headers["Location"]) == (302, "/")


# The pool


def test_in_suggest_the_pencil_sits_on_every_withdrawable_card_for_any_voter(dani, the_thing, cube):
    assert pencils_on(dani.get("/").text) == [cube.pk, the_thing.pk]


def test_in_suggest_the_pencil_is_absent_from_an_approved_card(dani, the_thing, cube):
    approve(the_thing)

    assert pencils_on(dani.get("/").text) == [cube.pk]


def test_in_approve_the_pencil_is_absent_everywhere(dani, the_thing, cube):
    walk_to(Phase.APPROVE)

    page = dani.get("/").text

    assert f'data-suggestion="{the_thing.pk}"' in page
    assert pencils_on(page) == []


def test_a_corrected_runtime_shows_by_hand_in_the_pool(dani, the_thing):
    correct(dani, the_thing, "127")

    assert text(runtime_line(dani.get("/").text)) == "127 min by hand ✎"
