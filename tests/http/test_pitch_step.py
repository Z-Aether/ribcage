"""The pitch step: choosing a picker tile fetches the film once, and Add suggests it with a pitch and a runtime (#5, #21, #26, #93)."""

import html
import re
from dataclasses import replace

import pytest
from django.core import signing

from ribcage.films import client, signed
from ribcage.films.film import RuntimeSource
from ribcage.films.tmdb import film_from_detail
from ribcage.phase.order import Phase
from ribcage.seeding.recorded import RecordedTmdb
from ribcage.suggestions import notes, runtime
from ribcage.suggestions.models import Approval, Note, Suggestion
from ribcage.suggestions.views import suggest
from tests.films import a_tmdb_film
from tests.http.test_phase import walk_to

SUGGEST = "/suggest/"
HTMX = {"HX-Request": "true"}
OUTAGE = "TMDB isn't answering right now. Try again in a bit, or add it by hand."
EVIL_DEAD = 109428
EVIL_DEAD_BURN = 1212763
PITCH = "Cabin, book, chainsaw. What more do you want?"


@pytest.fixture(scope="module")
def recordings():
    return RecordedTmdb()


class Counted:
    """The recordings as TMDB, counting what was asked of it."""

    def __init__(self, recordings, detail=None):
        self.recordings = recordings
        self.detail = detail
        self.asked = []

    def __call__(self, path, parameters, headers):
        self.asked.append((path, parameters))
        if self.detail is not None:
            return self.detail
        return self.recordings(path, parameters, headers)


@pytest.fixture
def tmdb(monkeypatch, recordings):
    # The tests run with DEBUG off, so the real transport is the one the client reaches: it answers from the recordings.
    transport = Counted(recordings)
    monkeypatch.setattr(client, "over_the_network", transport)
    return transport


@pytest.fixture
def failing(monkeypatch):
    def unreachable(path, parameters, headers):
        raise TimeoutError

    monkeypatch.setattr(client, "over_the_network", unreachable)


@pytest.fixture
def hanna(client, voters):
    client.force_login(voters["Hanna"])
    return client


def step(client, tmdb_id, headers=HTMX):
    return client.get(SUGGEST, {"tmdb_id": tmdb_id}, headers=headers)


def signed_film_in(page):
    return html.unescape(re.search(r'<input type="hidden" name="film" value="([^"]*)">', page)[1])


def add(client, film, pitch=PITCH, runtime_typed=None, headers=HTMX):
    signed_film = film if isinstance(film, str) else signed.signed(film)
    form = {"film": signed_film, "pitch": pitch}
    if runtime_typed is not None:
        form["runtime"] = runtime_typed
    return client.post(SUGGEST, form, headers=headers)


def recorded_film(recordings, tmdb_id):
    return film_from_detail(recordings.details[tmdb_id])


def text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def runtime_line(page):
    return re.search(r'<div class="film-card__runtime[^"]*" data-runtime>.*?</div>', page, re.S)[0]


def typed_runtime(page):
    return html.unescape(re.search(r'<input [^>]*name="runtime"[^>]*value="([^"]*)"', page)[1])


def typed_pitch(page):
    return html.unescape(re.search(r'<textarea name="pitch"[^>]*>(.*?)</textarea>', page, re.S)[1])


def refusals(page):
    return [html.unescape(said) for said in re.findall(r'<p class="(?:pitch-step__refusal|runtime__refusal)" role="status">(.*?)</p>', page, re.S)]


def cards(page):
    return re.findall(r'<article class="film-card[^"]*" data-film-card data-suggestion="(\d+)"[^>]*>.*?</article>', page, re.S)


def card_of(page, suggestion):
    return re.search(rf'<article class="film-card[^"]*" data-film-card data-suggestion="{suggestion.pk}"[^>]*>.*?</article>', page, re.S)[0]


def test_add_is_windowed_to_suggest_and_approve():
    # Suggesting is only offered in SUGGEST; APPROVE's window just catches a stale tab (#34).
    assert suggest.phase_window == {Phase.SUGGEST, Phase.APPROVE}


# The step


def test_a_tile_not_in_the_pool_leads_to_the_step_and_one_in_the_pool_does_not(hanna, voters, tmdb):
    Suggestion.objects.suggest(voters["ada"], a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), "Burn it all.")

    page = hanna.get("/find/", {"q": "evil dead"}, headers=HTMX).text

    tile = re.search(rf'<button [^>]*data-tmdb-id="{EVIL_DEAD}"[^>]*>', page)[0]
    assert f'hx-get="/suggest/?tmdb_id={EVIL_DEAD}"' in tile
    assert 'hx-target="#picker"' in tile
    assert "hx-get" not in re.search(rf'<button [^>]*data-tmdb-id="{EVIL_DEAD_BURN}"[^>]*>', page)[0]


def test_the_step_makes_the_films_one_detail_fetch_in_en_us(hanna, tmdb):
    step(hanna, EVIL_DEAD)

    assert tmdb.asked == [(f"/movie/{EVIL_DEAD}", {"language": "en-US", "append_to_response": "credits,videos,release_dates", "api_key": "your-tmdb-api-key"})]


def test_the_step_shows_the_film_an_autofocused_pitch_box_and_the_runtime_line(hanna, tmdb):
    page = step(hanna, EVIL_DEAD).text

    assert '<img class="poster poster--card"' in page
    assert text(re.search(r'<h3 class="pitch-step__title">.*?</h3>', page, re.S)[0]) == "Evil Dead 2013"
    assert text(re.search(r'<p class="film-card__meta">.*?</p>', page, re.S)[0]) == "Fede Álvarez R"
    assert re.search(r'<textarea name="pitch"[^>]*autofocus', page)
    assert typed_pitch(page) == ""
    line = runtime_line(page)
    assert text(re.sub(r"<label .*?</label>", "", line, flags=re.S)) == "Runtime 91 min TMDB ✎"
    assert re.search(r'<label class="runtime__field" hidden>', line)
    assert typed_runtime(page) == "91"
    assert ">Add</button>" in page


def test_with_no_runtime_from_tmdb_the_box_is_open_and_empty_from_the_start(hanna, monkeypatch, recordings):
    detail = recordings.details[EVIL_DEAD] | {"runtime": 0}
    monkeypatch.setattr(client, "over_the_network", Counted(recordings, detail))

    line = runtime_line(step(hanna, EVIL_DEAD).text)

    assert "runtime__pencil" not in line
    assert re.search(r'<label class="runtime__field">', line)
    assert typed_runtime(line) == ""


def test_a_failing_detail_fetch_shows_the_outage_message(hanna, failing):
    response = step(hanna, EVIL_DEAD)

    assert response.status_code == 200
    assert OUTAGE in response.text
    assert "pitch-step" not in response.text


def test_a_malformed_detail_shows_the_outage_message(hanna, monkeypatch, recordings):
    monkeypatch.setattr(client, "over_the_network", Counted(recordings, {"id": EVIL_DEAD, "title": "Evil Dead"}))

    assert OUTAGE in step(hanna, EVIL_DEAD).text


@pytest.mark.parametrize("phase", [Phase.APPROVE, Phase.VOTE, Phase.PICK, Phase.RUN])
def test_the_steps_get_from_outside_suggest_reloads_the_tab(hanna, tmdb, phase):
    walk_to(phase)

    response = step(hanna, EVIL_DEAD)

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")
    assert tmdb.asked == []


def test_a_plain_get_of_the_step_from_before_htmx_loaded_is_sent_to_the_phase_page(hanna, tmdb):
    response = step(hanna, EVIL_DEAD, headers={})

    assert (response.status_code, response["Location"]) == (302, "/")
    assert tmdb.asked == []


@pytest.mark.parametrize("tmdb_id", ["", "evil", "-5", "0"])
def test_a_step_for_no_film_is_a_bad_request(hanna, tmdb, tmdb_id):
    assert step(hanna, tmdb_id).status_code == 400
    assert tmdb.asked == []


# Add, over the recorded details


def test_add_stores_what_film_from_detail_reads_with_tmdbs_runtime_in_both_fields(hanna, voters, tmdb, recordings):
    signed_film = signed_film_in(step(hanna, EVIL_DEAD).text)

    add(hanna, signed_film, runtime_typed="91")

    suggestion = Suggestion.objects.get()
    assert suggestion.film == recorded_film(recordings, EVIL_DEAD)
    assert (suggestion.runtime, suggestion.tmdb_runtime) == (91, 91)
    assert (suggestion.suggester, suggestion.suggester_name, suggestion.approval) == (voters["Hanna"], "Hanna", Approval.UNDECIDED)
    assert [(note.author, note.text) for note in Note.objects.all()] == [(voters["Hanna"], PITCH)]


def test_a_runtime_edited_at_the_step_is_stored_as_current_with_tmdbs_kept_and_reads_by_hand(hanna, tmdb, recordings):
    add(hanna, signed_film_in(step(hanna, EVIL_DEAD).text), runtime_typed="97")

    suggestion = Suggestion.objects.get()
    assert (suggestion.runtime, suggestion.tmdb_runtime) == (97, 91)
    assert suggestion.film == replace(recorded_film(recordings, EVIL_DEAD), runtime=97, runtime_source=RuntimeSource.HAND_ENTERED)
    assert text(runtime_line(card_of(hanna.get("/").text, suggestion))).startswith("97 min by hand")


def test_a_runtime_typed_for_a_film_tmdb_gave_none_reads_by_hand(hanna, recordings):
    film = replace(recorded_film(recordings, EVIL_DEAD), runtime=None)

    add(hanna, film, runtime_typed="91")

    suggestion = Suggestion.objects.get()
    assert (suggestion.runtime, suggestion.tmdb_runtime) == (91, None)


def test_add_asks_tmdb_nothing(hanna, tmdb, recordings):
    add(hanna, recorded_film(recordings, EVIL_DEAD), runtime_typed="91")

    assert tmdb.asked == []
    assert Suggestion.objects.count() == 1


def test_after_add_the_voter_is_back_at_the_pool_with_the_new_card_on_top(hanna, voters, recordings):
    older = Suggestion.objects.suggest(voters["ada"], a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), "Burn it all.")

    response = add(hanna, recorded_film(recordings, EVIL_DEAD), runtime_typed="91")

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")
    page = hanna.get("/").text
    assert cards(page) == [str(Suggestion.objects.get(tmdb_id=EVIL_DEAD).pk), str(older.pk)]
    assert text(runtime_line(card_of(page, Suggestion.objects.get(tmdb_id=EVIL_DEAD)))).startswith("91 min TMDB")


def test_a_plain_add_from_before_htmx_loaded_lands_on_the_pool(hanna, recordings):
    response = add(hanna, recorded_film(recordings, EVIL_DEAD), runtime_typed="91", headers={})

    assert (response.status_code, response["Location"]) == (302, "/")
    assert Suggestion.objects.count() == 1


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE])
def test_add_works_in_suggest_and_approve(hanna, recordings, phase):
    walk_to(phase)

    response = add(hanna, recorded_film(recordings, EVIL_DEAD), runtime_typed="91")

    assert response.headers["HX-Redirect"] == "/"
    assert Suggestion.objects.count() == 1


@pytest.mark.parametrize("phase", [Phase.VOTE, Phase.PICK, Phase.RUN])
def test_add_is_refused_from_vote_on_with_the_reload(hanna, recordings, phase):
    walk_to(phase)

    response = add(hanna, recorded_film(recordings, EVIL_DEAD), runtime_typed="91")

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")
    assert Suggestion.objects.count() == 0


# Refusals


def test_a_tampered_signed_field_is_refused_and_nothing_is_stored(hanna, tmdb):
    signed_film = signed_film_in(step(hanna, EVIL_DEAD).text)
    tampered = signed_film[:10] + ("A" if signed_film[10] != "A" else "B") + signed_film[11:]

    response = add(hanna, tampered, runtime_typed="91")

    assert response.status_code == 400
    assert Suggestion.objects.count() == Note.objects.count() == 0


def test_a_film_signed_for_something_else_is_refused(hanna):
    response = add(hanna, signing.dumps({"tmdb_id": EVIL_DEAD, "title": "Evil Dead"}), runtime_typed="91")

    assert response.status_code == 400
    assert Suggestion.objects.count() == 0


@pytest.mark.parametrize("pitch", ["", "   \n  "], ids=["empty", "blank"])
def test_a_missing_pitch_is_refused_gently_keeping_the_runtime_typed(hanna, recordings, pitch):
    page = add(hanna, recorded_film(recordings, EVIL_DEAD), pitch=pitch, runtime_typed="97").text

    assert refusals(page) == [notes.PITCH_EMPTY]
    assert typed_pitch(page) == pitch
    assert typed_runtime(page) == "97"
    assert Suggestion.objects.count() == 0


def test_a_missing_runtime_is_refused_gently_keeping_the_pitch_typed(hanna, recordings):
    page = add(hanna, recorded_film(recordings, EVIL_DEAD), runtime_typed="").text

    assert refusals(page) == [runtime.EMPTY]
    assert typed_pitch(page) == PITCH
    assert re.search(r'<label class="runtime__field">', page)
    assert Suggestion.objects.count() == 0


def test_a_runtime_not_posted_at_all_is_refused(hanna, recordings):
    page = add(hanna, recorded_film(recordings, EVIL_DEAD)).text

    assert refusals(page) == [runtime.EMPTY]
    assert Suggestion.objects.count() == 0


@pytest.mark.parametrize(("typed", "said"), [("1h 30", runtime.NOT_WHOLE_MINUTES), ("0", runtime.NOT_POSITIVE), ("99999", runtime.TOO_LONG)])
def test_a_refused_runtime_is_refused_gently_keeping_both_typed(hanna, recordings, typed, said):
    page = add(hanna, recorded_film(recordings, EVIL_DEAD), runtime_typed=typed).text

    assert refusals(page) == [said]
    assert typed_runtime(page) == typed
    assert typed_pitch(page) == PITCH
    assert re.search(r'<label class="runtime__field">', page)
    assert Suggestion.objects.count() == 0


def test_a_missing_pitch_and_a_refused_runtime_are_said_together(hanna, recordings):
    page = add(hanna, recorded_film(recordings, EVIL_DEAD), pitch="", runtime_typed="soon").text

    assert refusals(page) == [notes.PITCH_EMPTY, runtime.NOT_WHOLE_MINUTES]


def test_a_pitch_over_the_cap_is_refused_whole_and_kept(hanna, recordings, settings):
    settings.NOTE_MAX_LENGTH = 20

    page = add(hanna, recorded_film(recordings, EVIL_DEAD), runtime_typed="91").text

    assert refusals(page) == [f"That's {len(PITCH)} characters, and a pitch holds 20. Trim it a little."]
    assert typed_pitch(page) == PITCH
    assert Suggestion.objects.count() == 0


def add_button(page):
    return re.search(r'<button type="submit" class="pitch-step__add"[^>]*>', page)[0]


def boxes_add_needs(page):
    return re.search(r'data-add-needs="([^"]*)"', add_button(page))[1].split()


def test_add_waits_in_the_browser_for_a_pitch_and_a_runtime_but_is_sent_enabled(hanna, tmdb):
    # The script disables Add until both are filled; without it Add posts and the server refuses (the dev, 2026-10-23).
    page = step(hanna, EVIL_DEAD).text

    assert boxes_add_needs(page) == ["pitch", "runtime"]
    assert "disabled" not in add_button(page)
    assert re.search(r"/static/suggest/pitch-step\.\w+\.js", hanna.get("/").text)


def test_a_refused_step_still_carries_the_signed_film_and_tmdbs_runtime_line(hanna, recordings):
    film = recorded_film(recordings, EVIL_DEAD)

    page = add(hanna, film, pitch="").text

    assert signed.unsigned(signed_film_in(page)) == film
    assert "pitch-step__title" in page


def test_a_pitch_refused_with_tmdbs_runtime_untouched_leaves_the_line_closed(hanna, recordings):
    page = add(hanna, recorded_film(recordings, EVIL_DEAD), pitch="", runtime_typed="91").text

    assert re.search(r'<label class="runtime__field" hidden>', page)


# Already suggested


@pytest.fixture
def burn_by_ada(voters):
    return Suggestion.objects.suggest(voters["ada"], a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), "Burn it all.")


def test_a_film_already_in_the_pool_makes_no_second_suggestion(hanna, burn_by_ada):
    response = add(hanna, a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), pitch="Me too!", runtime_typed="110")

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")
    assert list(Suggestion.objects.all()) == [burn_by_ada]
    assert Note.objects.filter(suggestion=burn_by_ada).count() == 1


def test_a_film_already_in_the_pool_opens_its_card_with_the_typed_text_in_its_box_unsaved(hanna, voters, burn_by_ada):
    add(hanna, a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), pitch="Me too!", runtime_typed="")

    card = card_of(hanna.get("/").text, burn_by_ada)
    assert card.startswith('<article class="film-card is-open"')
    assert re.search(r'<textarea name="text" rows="3" autofocus>Me too!</textarea>', card)
    assert "ada suggested it first, so your words are here, not yet saved." in card
    assert not Note.objects.filter(author=voters["Hanna"]).exists()


def test_the_kept_text_shows_once(hanna, burn_by_ada):
    add(hanna, a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), pitch="Me too!", runtime_typed="110")
    hanna.get("/")

    card = card_of(hanna.get("/").text, burn_by_ada)
    assert "is-open" not in card.split(">")[0]
    assert "Me too!" not in card


def test_a_plain_add_of_a_film_already_in_the_pool_lands_on_its_card_too(hanna, burn_by_ada):
    response = add(hanna, a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), pitch="Me too!", runtime_typed="110", headers={})

    assert response["Location"] == "/"
    assert "Me too!</textarea>" in card_of(hanna.get("/").text, burn_by_ada)


def test_kept_words_go_under_a_note_the_voter_already_saved_and_neither_is_saved(hanna, voters, burn_by_ada):
    Note.objects.create(suggestion=burn_by_ada, author=voters["Hanna"], text="I'm in.")

    add(hanna, a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), pitch="Me too!", runtime_typed="110")

    card = card_of(hanna.get("/").text, burn_by_ada)
    assert re.search(r"<textarea name=\"text\" rows=\"3\" autofocus>I&#x27;m in.\n\nMe too!</textarea>", card)
    assert "ada suggested it first, so your words are under your note, not yet saved." in card
    assert Note.objects.get(author=voters["Hanna"]).text == "I'm in."


def test_kept_words_on_your_own_film_go_under_your_pitch(hanna, voters, recordings):
    film = recorded_film(recordings, EVIL_DEAD)
    add(hanna, film, runtime_typed="91")

    add(hanna, film, pitch="Again!", runtime_typed="91")

    card = html.unescape(card_of(hanna.get("/").text, Suggestion.objects.get()))
    assert f"autofocus>{PITCH}\n\nAgain!</textarea>" in card
    assert "You've already suggested it, so your words are under your pitch, not yet saved." in card
    assert Note.objects.get(author=voters["Hanna"]).text == PITCH


@pytest.mark.parametrize("pitch", ["", "  \r\n "])
def test_a_blank_kept_pitch_leaves_the_box_as_it_was(hanna, voters, burn_by_ada, pitch):
    Note.objects.create(suggestion=burn_by_ada, author=voters["Hanna"], text="I'm in.")

    add(hanna, a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), pitch=pitch, runtime_typed="110")

    card = html.unescape(card_of(hanna.get("/").text, burn_by_ada))
    assert card.startswith('<article class="film-card is-open"')
    assert "autofocus>I'm in.</textarea>" in card
    assert "ada suggested it first." in card
