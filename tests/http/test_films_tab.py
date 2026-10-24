"""The Films tab's ledger: one row per suggestion, four filters with their counts, and the ballot's screen time (#28, #95)."""

import html
import re
from itertools import count

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.identity.removal import remove
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Suggestion
from tests.films import CABINET_OF_CURIOSITIES, THE_SHINING, a_tmdb_film
from tests.http.test_pool import walk_to
from tests.http.test_roster_tab import text

TAB = "/console/films/"
UNDECIDED, APPROVED, DROPPED = Approval.UNDECIDED, Approval.APPROVED, Approval.DROPPED
TMDB_IDS = count(1)


def suggested(voter, title, approval=UNDECIDED, runtime=100):
    suggestion = Suggestion.objects.suggest(voter, a_tmdb_film(next(TMDB_IDS), title, runtime), f"A pitch for {title}.")
    if approval != UNDECIDED:
        suggestion.approval = approval
        suggestion.save(update_fields=["approval"])
    return suggestion


@pytest.fixture
def pool(voters):
    # Oldest first: three approved, two undecided, one dropped.
    ada, hanna = voters["ada"], voters["Hanna"]
    return [
        suggested(ada, "The Thing", APPROVED, runtime=109),
        suggested(hanna, "Cube", UNDECIDED, runtime=90),
        suggested(ada, "The Shining", APPROVED, runtime=144),
        suggested(hanna, "Pulse", DROPPED, runtime=119),
        suggested(hanna, "Possession", UNDECIDED, runtime=124),
        suggested(ada, "Suspiria", APPROVED, runtime=99),
    ]


def rows(page):
    """Each row's cells as text: the film, the suggester, the notes, the runtime and the approval."""
    found = re.findall(r"<tr data-suggestion=\"\d+\" data-ledger-row>(.*?)</tr>", page, re.S)
    return [[text(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)[1:]] for row in found]


def titles(page):
    return [html.unescape(title) for title in re.findall(r'<button type="button" class="ledger__title ledger__opens"[^>]*>([^<]+)</button>', page)]


def filters(page):
    """Each filter link: its label and count, where it leads, and whether it is the chosen one."""
    nav = re.search(r'<nav class="films-filters" aria-label="Show">(.*?)</nav>', page, re.S)[1]
    found = re.findall(r'<a href="([^"]+)"( aria-current="page")?>(.*?)</a>', nav, re.S)
    return [(text(label), html.unescape(href), bool(current)) for href, current, label in found]


def summary(page):
    return text(re.search(r'<p class="films-summary">(.*?)</p>', page, re.S)[1])


def opened_card(page, suggestion):
    return re.search(rf'<tr class="ledger__detail" id="film-{suggestion.pk}" hidden>(.*?)</tr>', page, re.S)[1]


@pytest.fixture(autouse=True)
def _in_approve(db):
    walk_to(Phase.APPROVE)


def test_the_rows_come_newest_first(admin, pool):
    assert titles(admin.get(TAB).text) == ["Suspiria", "Possession", "Pulse", "The Shining", "Cube", "The Thing"]


def test_a_row_shows_the_film_its_suggester_its_notes_its_runtime_and_its_approval(admin, voters, pool):
    thing = pool[0]
    thing.notes.create(author=voters["Hanna"], text="Yes.")
    thing.notes.create(author=voters["Dani"], text="Please.")

    shown = rows(admin.get(TAB).text)

    assert shown[-1] == ["The Thing 2000", "ada", "3", "109 TMDB", "approved"]
    assert shown[-2] == ["Cube 2000", "Hanna", "1", "90 TMDB", "undecided"]
    assert shown[2] == ["Pulse 2000", "Hanna", "1", "119 TMDB", "dropped"]


def test_the_approval_column_is_named_approval_not_state(admin, pool):
    page = admin.get(TAB).text

    assert '<th scope="col">Approval</th>' in page
    assert 'class="approval-tag approval-tag--approved"' in page
    assert "state" not in page.lower().replace("statement", "")


def test_a_row_shows_the_director_and_a_runtime_by_hand(admin, voters):
    Suggestion.objects.suggest(voters["ada"], THE_SHINING, "Pitch.", runtime=146)
    Suggestion.objects.suggest(voters["ada"], CABINET_OF_CURIOSITIES, "Pitch.")

    assert [row[0::3] for row in rows(admin.get(TAB).text)] == [
        ["Cabinet of Curiosities", "47 by hand"],
        ["The Shining 1980 Stanley Kubrick", "146 by hand"],
    ]


def test_a_removed_suggesters_row_shows_their_kept_name_marked_removed(admin, voters, pool):
    remove(voters["Hanna"])

    page = admin.get(TAB).text

    assert [row[1] for row in rows(page)] == ["ada", "Hanna removed", "Hanna removed", "ada", "Hanna removed", "ada"]
    assert 'Hanna <span class="removed-tag">removed</span>' in page


@pytest.mark.parametrize(
    "show, shown, chosen",
    [
        (None, ["Suspiria", "Possession", "Pulse", "The Shining", "Cube", "The Thing"], "All 6"),
        ("undecided", ["Possession", "Cube"], "Undecided 2"),
        ("approved", ["Suspiria", "The Shining", "The Thing"], "On the ballot 3"),
        ("dropped", ["Pulse"], "Dropped 1"),
    ],
)
def test_each_filters_link_shows_its_rows_and_its_count(admin, pool, show, shown, chosen):
    page = admin.get(TAB).text
    link = next(href for label, href, _ in filters(page) if label == chosen)

    filtered = admin.get(link).text

    assert link == TAB if show is None else link == f"{TAB}?show={show}"
    assert titles(filtered) == shown
    assert [label for label, _, current in filters(filtered) if current] == [chosen]
    assert [label for label, _, _ in filters(filtered)] == ["All 6", "Undecided 2", "On the ballot 3", "Dropped 1"]


@pytest.mark.parametrize("show", ["", "everything", "UNDECIDED"])
def test_a_show_that_names_no_filter_shows_all(admin, pool, show):
    page = admin.get(TAB, {"show": show}).text

    assert len(titles(page)) == 6
    assert [label for label, _, current in filters(page) if current] == ["All 6"]


@pytest.mark.parametrize(
    "show, says",
    [(None, "Nobody has suggested a film."), ("undecided", "No film is undecided."), ("approved", "No film is on the ballot."), ("dropped", "No film is dropped.")],
)
def test_a_filter_with_no_rows_says_so(admin, show, says):
    page = admin.get(TAB, {"show": show} if show else {}).text

    assert '<table class="ledger films-ledger"' not in page
    assert f"<p>{says}</p>" in page


def test_the_summary_counts_the_approved_films_and_sums_their_runtimes(admin, pool):
    # 109 + 144 + 99 minutes approved; the undecided and dropped films' runtimes are left out.
    assert summary(admin.get(TAB).text) == "On the ballot: 3 films · 5 h 52 min screen time"


def test_the_summary_is_the_ballots_under_every_filter(admin, pool):
    assert summary(admin.get(TAB, {"show": "dropped"}).text) == "On the ballot: 3 films · 5 h 52 min screen time"


def test_the_summary_of_an_empty_ballot(admin, voters):
    suggested(voters["ada"], "Cube")

    assert summary(admin.get(TAB).text) == "On the ballot: 0 films · 0 min screen time"


def test_the_summary_of_one_film_under_an_hour(admin, voters):
    suggested(voters["ada"], "Short", APPROVED, runtime=47)

    assert summary(admin.get(TAB).text) == "On the ballot: 1 film · 47 min screen time"


def test_the_title_opens_a_card_with_no_note_box_withdraw_or_pencil(admin, voters, pool):
    cube = pool[1]
    cube.notes.create(author=voters["ada"], text="Ada on Cube.")

    page = admin.get(TAB).text
    card = opened_card(page, cube)

    assert f'aria-controls="film-{cube.pk}">Cube</button>' in page
    assert 'class="film-card is-open"' in card
    assert "A pitch for Cube." in card and "Ada on Cube." in card
    assert "note-box" not in card and "<textarea" not in card and "<form" not in card
    assert "Withdraw" not in card
    assert "runtime__pencil" not in card
    assert '<div class="film-card__phase-bar" data-phase-bar></div>' in card


def test_the_card_lists_every_note(admin, voters, pool):
    cube = pool[1]
    for name in ["ada", "Dani"]:
        cube.notes.create(author=voters[name], text=f"{name} on Cube.")

    card = opened_card(admin.get(TAB).text, cube)

    assert re.findall(r"(\w+) on Cube\.", card) == ["ada", "Dani"]


def test_the_page_makes_as_many_queries_for_a_large_pool_as_for_a_small_one(admin, voters):
    def queries_for_the_tab():
        with CaptureQueriesContext(connection) as captured:
            assert admin.get(TAB).status_code == 200
        return len(captured)

    suggested(voters["ada"], "One").notes.create(author=voters["Hanna"], text="In.")
    small = queries_for_the_tab()
    for title, approval in [("Two", APPROVED), ("Three", DROPPED), ("Four", UNDECIDED), ("Five", APPROVED)]:
        suggestion = suggested(voters["Dani"], title, approval)
        suggestion.notes.create(author=voters["Hanna"], text="In.")
        suggestion.notes.create(author=voters["ada"], text="Me too.")
    remove(voters["Dani"])

    assert queries_for_the_tab() == small
