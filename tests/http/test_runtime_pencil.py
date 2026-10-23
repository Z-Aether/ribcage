"""The runtime pencil: any voter correcting a film's runtime for the copy the group will watch, in SUGGEST,
on a film nothing downstream holds, inline on the card's runtime line (#21, #27, #34, #90)."""

import html
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.phase.order import Phase
from ribcage.suggestions import runtime
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.suggestions.views import correct_runtime
from tests.films import CABINET_OF_CURIOSITIES, a_tmdb_film
from tests.http.test_phase import walk_to
from tests.http.test_phase_check import send

RUNTIME = "/runtime/"
HTMX = {"HX-Request": "true"}
OUTSIDE_THE_WINDOW = [Phase.APPROVE, Phase.VOTE, Phase.PICK, Phase.RUN]


@pytest.fixture
def the_thing(voters):
    # Hanna's suggestion, as TMDB gave it: 109 minutes.
    return Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing", runtime=109), "Lights off.")


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


def correct(client, suggestion, typed, headers=HTMX):
    named = suggestion if isinstance(suggestion, str) else suggestion.pk
    return client.post(RUNTIME, {"suggestion": named, "runtime": typed}, headers=headers)


def open_pencil(client, suggestion, headers=HTMX, **extra):
    return client.get(RUNTIME, {"suggestion": suggestion.pk, **extra}, headers=headers)


def runtimes(suggestion):
    suggestion.refresh_from_db()
    return suggestion.runtime, suggestion.tmdb_runtime


def approve(suggestion):
    Suggestion.objects.filter(pk=suggestion.pk).update(approval=Approval.APPROVED)


def text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def runtime_line(page):
    return re.search(r'<div class="film-card__runtime[^"]*" data-runtime>.*?</div>', page, re.S)[0]


def typed_in(line):
    return html.unescape(re.search(r'<input [^>]*name="runtime"[^>]*value="([^"]*)"', line)[1])


def refusal(line):
    found = re.search(r'<p class="runtime__refusal" role="status">(.*?)</p>', line, re.S)
    return html.unescape(found[1]) if found else None


def pencils_on(page):
    """The suggestion of each card in the page whose runtime line carries the pencil."""
    cards = re.findall(r'<article class="film-card[^"]*" data-film-card data-suggestion="(\d+)">(.*?)</article>', page, re.S)
    return [int(pk) for pk, shown in cards if "runtime__pencil" in runtime_line(shown)]


def test_the_pencil_is_windowed_to_suggest():
    assert correct_runtime.phase_window == {Phase.SUGGEST}


@pytest.mark.parametrize("voter", ["hanna", "dani"], ids=["the suggester", "another voter"])
def test_any_voter_corrects_the_runtime_of_a_withdrawable_film_in_suggest(request, the_thing, voter):
    client = request.getfixturevalue(voter)

    response = correct(client, the_thing, "127")

    assert response.status_code == 200
    assert runtimes(the_thing) == (127, 109)


def test_the_answer_is_the_runtime_line_alone_showing_the_correction_by_hand(dani, the_thing):
    response = correct(dani, the_thing, "127")

    # Only the line is swapped, so a note being typed on the same card is left alone (#90).
    assert response.text.count("<div class=\"film-card__runtime") == 1
    assert "<article" not in response.text
    assert text(runtime_line(response.text)) == "127 min by hand ✎"
    assert "runtime__pencil" in response.text


def test_tmdbs_runtime_is_kept_unchanged(dani, the_thing):
    correct(dani, the_thing, "127")
    correct(dani, the_thing, "140")

    assert Suggestion.objects.get(pk=the_thing.pk).tmdb_runtime == 109


def test_a_correction_back_to_tmdbs_runtime_reads_as_tmdbs_again(dani, the_thing):
    correct(dani, the_thing, "127")

    response = correct(dani, the_thing, "109")

    assert text(runtime_line(response.text)) == "109 min TMDB ✎"


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


def test_an_approved_film_is_refused_and_answered_with_its_line_offering_no_pencil(dani, the_thing):
    approve(the_thing)

    response = correct(dani, the_thing, "127")

    assert runtimes(the_thing) == (109, 109)
    # The pencil leaves the line, with no explanation (#27).
    assert text(runtime_line(response.text)) == "109 min TMDB"
    assert "runtime__pencil" not in response.text


@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
def test_an_htmx_correction_outside_suggest_writes_nothing_and_reloads_the_tab(dani, the_thing, phase):
    walk_to(phase)

    response = correct(dani, the_thing, "127")

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")
    assert runtimes(the_thing) == (109, 109)


@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
def test_a_plain_correction_outside_suggest_writes_nothing_and_is_sent_to_the_phase_page(dani, the_thing, phase):
    walk_to(phase)

    response = correct(dani, the_thing, "127", headers={})

    assert (response.status_code, response.headers["Location"]) == (302, "/")
    assert runtimes(the_thing) == (109, 109)


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
def test_a_runtime_that_isnt_positive_whole_minutes_is_refused_gently_and_left_as_typed(dani, the_thing, typed, said):
    response = correct(dani, the_thing, typed)

    assert response.status_code == 200
    assert runtimes(the_thing) == (109, 109)
    line = runtime_line(response.text)
    assert (typed_in(line), refusal(line)) == (typed, said)


def test_a_plain_correction_writes_and_is_sent_to_the_phase_page(dani, the_thing):
    response = correct(dani, the_thing, "127", headers={})

    assert (response.status_code, response.headers["Location"]) == (302, "/")
    assert runtimes(the_thing) == (127, 109)


@pytest.mark.parametrize("named", ["999", "not-a-number", ""])
def test_a_correction_naming_no_suggestion_writes_nothing_and_reloads_the_tab(dani, the_thing, named):
    response = correct(dani, named, "127")

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")
    assert runtimes(the_thing) == (109, 109)


@pytest.mark.parametrize("method", ["options", "trace", "put", "patch", "delete"])
@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.VOTE])
def test_the_runtime_route_answers_every_method_but_get_head_and_post_with_405(dani, the_thing, method, phase):
    walk_to(phase)

    response = send(dani, method, RUNTIME, f"suggestion={the_thing.pk}&runtime=127")

    assert response.status_code == 405
    assert runtimes(the_thing) == (109, 109)


# Opening the pencil


def test_opening_the_pencil_writes_nothing(dani, the_thing):
    with CaptureQueriesContext(connection) as captured:
        response = open_pencil(dani, the_thing)

    assert response.status_code == 200
    assert [query["sql"] for query in captured if not query["sql"].lstrip().upper().startswith("SELECT")] == []


def test_the_open_pencil_edits_the_current_runtime_on_its_line(dani, the_thing):
    line = runtime_line(open_pencil(dani, the_thing).text)

    assert f'<input type="hidden" name="suggestion" value="{the_thing.pk}">' in line
    assert typed_in(line) == "109"
    assert refusal(line) is None
    assert re.search(r'<button type="submit"[^>]*>Save</button>', line)


def test_cancel_closes_the_line_and_offers_the_pencil_again(dani, the_thing):
    line = runtime_line(open_pencil(dani, the_thing, cancel="").text)

    assert "<form" not in line
    assert text(line) == "109 min TMDB ✎"


def test_cancel_is_the_closed_address(dani, the_thing):
    line = runtime_line(open_pencil(dani, the_thing).text)

    assert f'hx-get="/runtime/?suggestion={the_thing.pk}&amp;cancel"' in line


def test_the_pencil_and_its_box_share_an_id_so_focus_moves_between_them(dani, the_thing):
    closed = runtime_line(open_pencil(dani, the_thing, cancel="").text)
    opened = runtime_line(open_pencil(dani, the_thing).text)

    focus = f'id="runtime-{the_thing.pk}"'
    assert re.search(rf'<a class="runtime__pencil"[^>]*{focus}', closed)
    assert re.search(rf'<input [^>]*{focus}[^>]*name="runtime"', opened)


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
