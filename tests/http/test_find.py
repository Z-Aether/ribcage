"""Find and the picker: the Suggest a film panel's first two steps, over TMDB's recorded answers (#5, #21, #25, #57, #92)."""

import html
import re

import pytest

from ribcage.films import client
from ribcage.phase.order import Phase
from ribcage.seeding.recorded import RecordedTmdb
from ribcage.suggestions.models import Suggestion
from ribcage.suggestions.views import find
from tests.films import a_tmdb_film
from tests.http.test_phase import walk_to

FIND = "/find/"
HTMX = {"HX-Request": "true"}
OUTAGE = "TMDB isn't answering right now. Try again in a bit, or add it by hand."
NO_RESULTS = "TMDB has no film by that title."
EVIL_DEAD_BURN = 1212763
# A v4 read token's shape, so the key would travel in a header, and a v3 key's, which would travel in the URL.
KEYS = ["eyJhbGciOiJIUzI1NiJ9.eyJzZWNyZXQiOiJrZXkifQ.c2lnbmVkLXNlY3JldA", "f00dfacef00dfacef00dfacef00dface"]


@pytest.fixture(scope="module")
def recordings():
    return RecordedTmdb()


@pytest.fixture
def recorded(monkeypatch, recordings):
    # The tests run with DEBUG off, so the real transport is the one the client reaches: it answers from the recordings.
    monkeypatch.setattr(client, "over_the_network", recordings)


@pytest.fixture
def failing(monkeypatch):
    def unreachable(path, parameters, headers):
        raise TimeoutError

    monkeypatch.setattr(client, "over_the_network", unreachable)


@pytest.fixture
def hanna(client, voters):
    client.force_login(voters["Hanna"])
    return client


def search(client, text, headers=HTMX):
    return client.get(FIND, {"q": text}, headers=headers)


def tiles(page):
    return [int(tmdb_id) for tmdb_id in re.findall(r'<button type="button" class="tile[^"]*" data-tmdb-id="(\d+)"', page)]


def tile(page, tmdb_id):
    found = re.search(rf'<button type="button" class="tile[^"]*" data-tmdb-id="{tmdb_id}".*?</button>', page, re.S)
    return found[0]


def text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def test_find_is_a_read():
    assert getattr(find, "phase_window", None) is None


@pytest.mark.parametrize(
    ("typed", "first_five"),
    [
        ("evil dead", [EVIL_DEAD_BURN, 109428, 713704, 764, 765]),
        ("insidious", [1291595, 49018, 91586, 1766192, 614479]),
        ("good boy", [1381027, 1422096, 983507, 21765, 1571169]),
        ("willy's wonderland", [643586]),
    ],
)
def test_a_recorded_search_shows_its_first_five_results_as_tiles_in_tmdbs_order(hanna, recorded, typed, first_five):
    response = search(hanna, typed)

    assert response.status_code == 200
    assert tiles(response.text) == first_five


def test_no_tile_is_chosen_and_the_picker_never_advances_on_its_own(hanna, recorded):
    page = search(hanna, "willy's wonderland").text

    assert tiles(page) == [643586]
    assert not re.search(r"aria-pressed=\"true\"|aria-selected|autofocus|checked|is-chosen|hx-trigger=\"load", page)


@pytest.mark.parametrize(("typed", "film"), [("mārama 2025", 1364953), ("insidious 2010", 49018), ("insidious 2008", 662095)])
def test_a_trailing_year_narrows_to_its_film(hanna, recorded, typed, film):
    assert tiles(search(hanna, typed).text) == [film]


def test_a_tile_shows_title_year_and_a_differing_original_title_and_no_runtime(hanna, recorded):
    page = search(hanna, "evil dead").text

    assert text(tile(page, 109428)) == "Evil Dead 2013"
    assert "min" not in text(tile(page, 109428))


def test_a_differing_original_title_shows_on_its_tile(hanna, recorded):
    page = search(hanna, "mārama").text

    assert text(tile(page, 889555)) == "Bright Star 2021 Whetū Mārama"


def test_a_posterless_result_shows_the_title_card(hanna, recorded):
    page = search(hanna, "killer klowns from outer space").text

    posterless = tile(page, 1464927)
    assert '<span class="poster poster--tile title-card">' in posterless
    assert "<img" not in posterless
    assert "<img" in tile(page, 16296)


def test_cabinet_of_curiosities_shows_no_results_not_the_outage(hanna, recorded):
    page = search(hanna, "Del Toro's Cabinet of Curiosities").text

    assert NO_RESULTS in page
    assert OUTAGE not in page
    assert tiles(page) == []


def test_a_failing_transport_shows_the_outage_message(hanna, failing):
    page = search(hanna, "evil dead").text

    assert OUTAGE in page
    assert NO_RESULTS not in page


@pytest.mark.parametrize("bad_result", [{"id": 1, "original_title": "X"}, "not a film", {"id": 1, "title": "X", "original_title": "X", "release_date": "soon"}])
def test_a_malformed_result_in_a_valid_reply_shows_the_outage_message(hanna, monkeypatch, bad_result):
    monkeypatch.setattr(client, "over_the_network", lambda path, parameters, headers: {"results": [bad_result]})

    response = search(hanna, "evil dead")

    assert response.status_code == 200
    assert OUTAGE in response.text


def test_an_unrecorded_search_shows_the_outage_message(hanna, recorded):
    assert OUTAGE in search(hanna, "blade runner 2049").text


def test_a_blank_search_shows_nothing(hanna, failing):
    response = search(hanna, "   ")

    assert (response.status_code, response.text) == (200, "")


def test_a_film_already_in_the_pool_is_marked_with_its_suggesters_name(hanna, voters, recorded):
    burn = Suggestion.objects.suggest(voters["ada"], a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), "Burn it all.")

    page = search(hanna, "evil dead").text

    marked = tile(page, EVIL_DEAD_BURN)
    assert text(marked).endswith("already suggested by ada")
    assert f'data-opens-suggestion="{burn.pk}"' in marked
    assert "already suggested" not in tile(page, 109428)
    assert "data-opens-suggestion" not in tile(page, 109428)


def test_a_removed_suggesters_film_keeps_their_name_on_its_tile(hanna, voters, recorded):
    Suggestion.objects.suggest(voters["ada"], a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), "Burn it all.")
    Suggestion.objects.filter(tmdb_id=EVIL_DEAD_BURN).update(suggester=None)

    assert text(tile(search(hanna, "evil dead").text, EVIL_DEAD_BURN)).endswith("already suggested by ada")


@pytest.mark.parametrize("phase", [Phase.APPROVE, Phase.VOTE, Phase.PICK, Phase.RUN])
def test_a_find_from_approve_or_later_reloads_the_tab(hanna, failing, phase):
    walk_to(phase)

    response = search(hanna, "evil dead")

    assert (response.status_code, response.headers["HX-Redirect"]) == (200, "/")


def test_a_plain_find_from_before_htmx_loaded_is_sent_to_the_phase_page(hanna, failing):
    response = search(hanna, "evil dead", headers={})

    assert (response.status_code, response["Location"]) == (302, "/")


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_find_answers_every_write_with_405(hanna, failing, method):
    assert getattr(hanna, method)(FIND, {"q": "evil dead"}).status_code == 405


def test_the_panel_shows_in_suggest_above_the_pools_filter(hanna):
    page = hanna.get("/").text

    assert page.index('<h2 id="suggest-a-film">Suggest a film</h2>') < page.index('<section class="pool"') < page.index("data-pool-filter")
    assert 'hx-get="/find/"' in page
    assert 'hx-trigger="input changed delay:350ms, search"' in page


@pytest.mark.parametrize("phase", [Phase.APPROVE, Phase.VOTE, Phase.PICK, Phase.RUN])
def test_the_panel_shows_in_suggest_alone(hanna, phase):
    walk_to(phase)

    page = hanna.get("/").text

    assert "Suggest a film" not in page
    assert "/find/" not in page


@pytest.mark.parametrize("key", KEYS)
def test_the_key_appears_in_no_response(hanna, voters, settings, recorded, key):
    settings.TMDB_API_KEY = key
    Suggestion.objects.suggest(voters["ada"], a_tmdb_film(EVIL_DEAD_BURN, "Evil Dead Burn"), "Burn it all.")

    responses = [hanna.get("/"), search(hanna, "evil dead"), search(hanna, "blade runner 2049"), search(hanna, "evil dead", headers={})]

    for response in responses:
        assert key not in response.content.decode()
        assert all(key not in value for value in response.headers.values())


def test_the_key_reaches_tmdb_in_the_request(hanna, settings, monkeypatch):
    settings.TMDB_API_KEY = KEYS[1]
    asked = []

    def transport(path, parameters, headers):
        asked.append(parameters)
        return {"results": []}

    monkeypatch.setattr(client, "over_the_network", transport)

    search(hanna, "evil dead")

    assert asked == [{"query": "evil dead", "language": "en-US", "api_key": KEYS[1]}]
