"""The film card's DoesTheDogDie section in the pool and under a Films tab row, the same for a voter and the admin (#21, #35 §2, #103)."""

import re
from itertools import pairwise

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from ribcage.phase.history import move
from ribcage.phase.order import PHASES, Phase
from ribcage.suggestions.models import Suggestion
from ribcage.triggers import client as dtdd_client
from ribcage.triggers import fetch
from tests.dtdd import Dtdd, detail, item
from tests.films import CABINET_OF_CURIOSITIES, THE_SHINING, a_tmdb_film

TAB = "/console/films/"
HTMX = {"HX-Request": "true"}
CREDIT = '<a href="https://www.doesthedogdie.com/">Powered by DoesTheDogDie.com</a>'
SHINING = item(12189, "The Shining", 1980)


def walk_to(phase):
    for before, after in pairwise(PHASES[: PHASES.index(phase) + 1]):
        move(before, after)


@pytest.fixture
def films(voters):
    """One film in each state: The Shining matched, Werewolf by Night uncovered, Weapons not fetched, Cabinet by hand."""
    ada = voters["ada"]
    shining = Suggestion.objects.suggest(ada, THE_SHINING, "Pitch.")
    werewolf = Suggestion.objects.suggest(ada, a_tmdb_film(894205, "Werewolf by Night"), "Pitch.")
    weapons = Suggestion.objects.suggest(ada, a_tmdb_film(1078605, "Weapons"), "Pitch.")
    cabinet = Suggestion.objects.suggest(ada, CABINET_OF_CURIOSITIES, "Pitch.")
    # Topic 999 is one the vocabulary doesn't name, so it stays off the card (#62).
    shining_dtdd = Dtdd(by_tmdb={THE_SHINING.tmdb_id: [SHINING]}, details=[detail(SHINING, (153, 3, 1), (200, 40, 2), (999, 5, 0))])
    fetch.look_up(shining, dtdd_client.Client("key", shining_dtdd))
    fetch.look_up(werewolf, dtdd_client.Client("key", Dtdd()))
    return {"matched": shining, "uncovered": werewolf, "not-fetched": weapons, "no-match": cabinet}


@pytest.fixture
def hanna(voters):
    client = Client()
    client.force_login(voters["Hanna"])
    return client


def card(page, suggestion):
    return re.search(rf'<article class="film-card[^"]*" data-film-card data-suggestion="{suggestion.pk}".*?</article>', page, re.S)[0]


def section(page, suggestion):
    found = re.search(r'<section class="film-card__dtdd.*?</section>', card(page, suggestion), re.S)
    return None if found is None else found[0]


def under_its_row(page, suggestion):
    return re.search(rf'<tr class="ledger__detail" id="film-{suggestion.pk}" hidden>(.*?)</tr>', page, re.S)[1]


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE])
def test_each_pool_card_carries_its_section_after_the_notes_with_one_credit_where_it_shows_dtdd_data(hanna, films, phase):
    walk_to(phase)
    page = hanna.get("/").text

    for state, suggestion in films.items():
        shown = card(page, suggestion)
        assert f'class="film-card__dtdd dtdd dtdd--{state}"' in shown
        assert shown.index("film-card__notes") < shown.index("film-card__dtdd") < shown.index("film-card__phase-bar")
        # A match or topics shown carries the credit; a gap with nothing of DoesTheDogDie's shown carries none (#21).
        assert shown.count(CREDIT) == (1 if state == "matched" else 0)


def test_a_matched_card_shows_its_record_auto_and_its_topic_count_behind_one_control(hanna, films):
    walk_to(Phase.SUGGEST)
    shown = section(hanna.get("/").text, films["matched"])

    assert '<a href="https://www.doesthedogdie.com/media/12189" target="_blank" rel="noopener">The Shining (1980)&nbsp;↗</a>' in shown
    assert '<span class="dtdd__set-by">auto</span>' in shown
    assert shown.count("<details") == 1
    assert "All 2 topics" in shown


def topic_rows(fragment):
    return re.findall(r'<span class="dtdd__label">([^<]+)</span> — <span class="dtdd__counts">([^<]+)</span>', fragment)


def test_the_list_fetches_its_named_topics_as_it_first_opens(hanna, films):
    walk_to(Phase.SUGGEST)
    shown = section(hanna.get("/").text, films["matched"])
    fetch_from = re.search(r'<details class="dtdd__topics"[^>]* hx-get="([^"]+)" hx-trigger="toggle once"', shown)[1]

    assert topic_rows(hanna.get(fetch_from.replace("&amp;", "&"), headers=HTMX).text) == [("dog death", "3 yes / 1 no"), ("jump scares", "40 yes / 2 no")]


@pytest.mark.parametrize("path", ["/", TAB])
def test_no_page_carries_any_films_topic_rows_however_many_it_has(hanna, admin, films, path):
    # A real film has 200 to 280 topics, so a pool of twenty carrying each list hidden ran past half a megabyte (#103).
    walk_to(Phase.APPROVE)
    page = (hanna if path == "/" else admin).get(path).text

    assert "dtdd__topic\"" not in page
    assert page.count('<p class="dtdd__fetching">') == 1


@pytest.mark.parametrize("phase", [phase for phase in PHASES if phase != Phase.RUN])
def test_a_voter_fetches_a_cards_list_in_any_phase_but_run(hanna, films, phase):
    walk_to(phase)

    assert len(topic_rows(hanna.get(f"/dtdd/?suggestion={films['matched'].pk}", headers=HTMX).text)) == 2


def test_the_admin_fetches_the_list_a_voter_does_from_the_consoles_own_route(admin, hanna, films):
    walk_to(Phase.APPROVE)
    tab = section(admin.get(TAB).text, films["matched"])

    assert f'hx-get="/console/films/dtdd/?suggestion={films["matched"].pk}"' in tab
    fetched = admin.get(f"/console/films/dtdd/?suggestion={films['matched'].pk}", headers=HTMX).text
    assert fetched == hanna.get(f"/dtdd/?suggestion={films['matched'].pk}", headers=HTMX).text


@pytest.mark.parametrize("path, lands_on", [("/dtdd/", "/"), ("/console/films/dtdd/", TAB)])
def test_a_plain_get_of_a_list_lands_on_its_page(hanna, admin, films, path, lands_on):
    client = hanna if path == "/dtdd/" else admin
    response = client.get(f"{path}?suggestion={films['matched'].pk}")

    assert response.status_code == 302
    assert response.url == lands_on


@pytest.mark.parametrize("path, lands_on", [("/dtdd/", "/"), ("/console/films/dtdd/", TAB)])
@pytest.mark.parametrize("named", ["", "nonsense", "99999"])
def test_a_list_for_a_film_gone_reloads_the_tab(hanna, admin, films, path, lands_on, named):
    client = hanna if path == "/dtdd/" else admin
    response = client.get(f"{path}?suggestion={named}", headers=HTMX)

    assert response.headers["HX-Redirect"] == lands_on


@pytest.mark.parametrize(
    "state, says",
    [
        ("uncovered", "DoesTheDogDie has no trigger data for this film"),
        ("not-fetched", "DoesTheDogDie didn&#x27;t answer. Trigger info will load later."),
        ("no-match", "Added by hand, so it has no DoesTheDogDie match yet."),
    ],
)
def test_each_gap_is_named_on_the_card_and_never_as_an_all_clear(hanna, films, state, says):
    walk_to(Phase.SUGGEST)
    shown = section(hanna.get("/").text, films[state])

    assert f'<span class="dtdd__gap-name">{state.replace("-", " ")}</span>' in shown
    assert says in shown
    assert "<details" not in shown


def test_a_collapsed_card_shows_neither_the_section_nor_its_credit():
    # The pool's cards open in place by script, so a collapsed card holds the section and the theme hides it whole (#21).
    css = open(finders.find("theme/theme.css"), encoding="utf-8").read()

    assert re.search(r"\.film-card:not\(\.is-open\) \.film-card__dtdd \{\s*display: none;", css)


def test_the_credit_sits_inside_the_section_so_a_collapsed_card_hides_it_too(hanna, films):
    walk_to(Phase.SUGGEST)
    shown = card(hanna.get("/").text, films["matched"])

    assert CREDIT in re.search(r'<section class="film-card__dtdd.*?</section>', shown, re.S)[0]
    assert shown.count(CREDIT) == 1


def test_the_card_a_note_swaps_in_keeps_its_section(hanna, films):
    walk_to(Phase.SUGGEST)
    pool_section = section(hanna.get("/").text, films["matched"])

    swapped = hanna.post("/note/", {"suggestion": films["matched"].pk, "text": "I'm in."}, headers=HTMX).text

    assert section(swapped, films["matched"]) == pool_section


@pytest.mark.parametrize("refused", [False, True], ids=["saved", "refused"])
def test_a_list_left_open_stays_open_with_its_rows_across_the_notes_swap(hanna, films, refused):
    # htmx keeps an hx-preserve element, open and with its fetched rows, where the swapped-in card has one of its id (#103).
    walk_to(Phase.SUGGEST)
    page = hanna.get("/").text
    form = re.search(r'<form class="note-box[^"]*"[^>]*>', card(page, films["matched"]))[0]
    assert 'hx-target="closest [data-film-card]"' in form

    text = "x" * (settings.NOTE_MAX_LENGTH + 1) if refused else "I'm in."
    swapped = hanna.post("/note/", {"suggestion": films["matched"].pk, "text": text}, headers=HTMX).text

    assert ("is-refusal" in swapped) == refused
    kept = re.search(r'<details class="dtdd__topics" id="([^"]+)" hx-preserve', swapped)[1]
    assert page.count(f'id="{kept}"') == 1
    assert f'<details class="dtdd__topics" id="{kept}" hx-preserve' in card(page, films["matched"])


def test_an_opened_card_under_a_films_tab_row_carries_the_section_and_one_credit(admin, films):
    walk_to(Phase.APPROVE)
    page = admin.get(TAB).text

    for state, suggestion in films.items():
        shown = under_its_row(page, suggestion)
        assert f'class="film-card__dtdd dtdd dtdd--{state}"' in shown
        assert shown.count(CREDIT) == (1 if state == "matched" else 0)


def test_the_admins_section_is_the_same_as_a_voters(admin, hanna, films):
    walk_to(Phase.APPROVE)
    pool, tab = hanna.get("/").text, admin.get(TAB).text

    # Only where each fetches the list from differs, the admin's behind the console's wall.
    for suggestion in films.values():
        assert section(tab, suggestion).replace("/console/films/dtdd/", "/dtdd/") == section(pool, suggestion)


def test_the_pool_reads_every_cards_section_in_as_many_queries_however_large(hanna, voters, films):
    walk_to(Phase.SUGGEST)

    def queries():
        with CaptureQueriesContext(connection) as captured:
            hanna.get("/")
        return len(captured)

    small = queries()
    for tmdb_id in range(1, 6):
        Suggestion.objects.suggest(voters["Dani"], a_tmdb_film(tmdb_id, f"Film {tmdb_id}"), "Pitch.")

    assert queries() == small
