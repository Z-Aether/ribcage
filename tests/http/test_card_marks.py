"""Vetoes and seen-its on every card, the admin's included, and counted on the Films tab (#128, #153)."""

import html
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.ballot.models import BallotRecord
from ribcage.identity.models import Voter
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Note
from tests.http.signing_in import PASSWORD
from tests.http.test_ballot_page import HTMX, film, signed_in
from tests.http.test_early_marks import save
from tests.http.test_films_tab import TAB, opened_card
from tests.http.test_phase import walk_to

CARD = "/ballot/card/"
EYE = "👁"


def mark(voter, suggestion, vetoed=False, seen=False):
    BallotRecord.objects.create(voter=voter, suggestion=suggestion, vetoed=vetoed, seen_it=seen)


@pytest.fixture
def everyone(voters):
    """Voters beyond the three the suite starts with: Bram, Cleo, Fen and Gus."""
    return {**voters, **{name: Voter.objects.create_voter(name, PASSWORD) for name in ["Bram", "Cleo", "Fen", "Gus"]}}


@pytest.fixture
def marked(everyone):
    """A film Hanna pitched, as ada, who marked nothing, sees others' marks on it.

    Hanna has seen it, Dani vetoes with a note and has seen it, Bram vetoes with no note and has seen it, Cleo vetoes with no note, and Fen and Gus have only seen it.
    """
    pitched = film(everyone["Hanna"], "One", Approval.APPROVED)
    Note.objects.create(suggestion=pitched, author=everyone["Hanna"], text="Spiders.")
    Note.objects.create(suggestion=pitched, author=everyone["Dani"], text="Too scary.")
    mark(everyone["Hanna"], pitched, seen=True)
    mark(everyone["Dani"], pitched, vetoed=True, seen=True)
    mark(everyone["Bram"], pitched, vetoed=True, seen=True)
    mark(everyone["Cleo"], pitched, vetoed=True)
    mark(everyone["Fen"], pitched, seen=True)
    mark(everyone["Gus"], pitched, seen=True)
    return {**everyone, "film": pitched, "client": signed_in(everyone["ada"])}


def pool_card(page, suggestion):
    return re.search(rf'<article class="film-card[^"]*" data-film-card data-suggestion="{suggestion.pk}".*?</article>', page, re.S)[0]


def lines(card):
    """The card's notes list as (classes, text, author line as read) per item; the Seen by line has no text and reads as it does."""
    found = []
    for classes, body in re.findall(r'<li class="(note[^"]*)">(.*?)</li>', re.search(r'<ul class="film-card__notes".*?</ul>', card, re.S)[0], re.S):
        words = re.search(r'<span class="note__full">(.*?)</span>', body, re.S) or re.search(r'<p class="note__text">(.*?)</p>', body, re.S)
        author = re.search(r'<span class="note__author">(.*)</span>', body) or re.search(r'<p class="seers[^"]*">(.*?)</p>', body)
        found.append((classes.split(), words[1] if words else "", " ".join(html.unescape(re.sub(r"<[^>]+>", "", author[1])).split())))
    return found


# What ada reads of `marked`, however the surface draws its card (#128, #153).
SEEN_BY_OTHERS = [
    (["note", "note--pitch"], "Spiders.", f"Hanna {EYE}"),
    (["note", "note--vetoed"], "Too scary.", f"vetoed by Dani {EYE}"),
    (["note", "note--vetoed", "note--bare"], "", f"Vetoed by Bram {EYE}"),
    (["note", "note--vetoed", "note--bare"], "", "Vetoed by Cleo"),
    (["note", "note--seers"], "", f"{EYE} Seen by Fen, Gus"),
]


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE])
def test_the_pools_card_marks_vetoers_and_seers_in_suggest_and_approve(marked, phase):
    walk_to(phase)

    card = pool_card(marked["client"].get("/").text, marked["film"])

    assert lines(card) == SEEN_BY_OTHERS


def test_votes_ballot_card_marks_them_and_its_bar_has_no_seen_by_line(marked):
    walk_to(Phase.VOTE)

    card = marked["client"].get(CARD, {"suggestion": str(marked["film"].pk)}, headers=HTMX).text

    assert lines(card) == SEEN_BY_OTHERS
    bar = re.search(r"data-vote-bar>(.*?)</form>\s*</div>", card, re.S)[1]
    assert "Seen by" not in bar and "vote-bar__line" not in card


def test_the_admins_films_tab_card_marks_them_too(marked, admin):
    card = opened_card(admin.get(TAB).text, marked["film"])

    assert lines(card) == SEEN_BY_OTHERS


def test_a_vetoer_who_has_seen_it_is_marked_and_left_off_the_seen_by_line(marked):
    card = pool_card(marked["client"].get("/").text, marked["film"])
    line = re.search(r'<span class="seers__all">(.*?)</span>', card)[1]

    assert line == "Fen, Gus" and "Dani" not in line and "Bram" not in line


def test_a_card_nobody_marks_has_no_mark_and_no_line(everyone):
    plain = film(everyone["Hanna"], "Plain", Approval.APPROVED)
    Note.objects.create(suggestion=plain, author=everyone["Hanna"], text="Nothing here.")

    card = pool_card(signed_in(everyone["ada"]).get("/").text, plain)

    assert lines(card) == [(["note", "note--pitch"], "Nothing here.", "Hanna")] and "note__seen" not in card and "Seen by" not in card


def test_a_suggester_with_a_blank_pitch_who_has_seen_it_is_on_the_seen_by_line(everyone):
    blank = film(everyone["Hanna"], "Blank", Approval.APPROVED)
    Note.objects.create(suggestion=blank, author=everyone["Hanna"], text="")
    mark(everyone["Hanna"], blank, seen=True)

    card = pool_card(signed_in(everyone["ada"]).get("/").text, blank)

    assert lines(card) == [(["note", "note--seers"], "", f"{EYE} Seen by Hanna")]


def test_the_viewers_own_marks_are_flagged_so_a_closed_card_lists_them_and_an_open_one_leaves_them_to_the_bar(marked):
    ada = marked["ada"]
    Note.objects.create(suggestion=marked["film"], author=ada, text="Mine.")
    mark(ada, marked["film"], vetoed=True, seen=True)

    shown = lines(pool_card(marked["client"].get("/").text, marked["film"]))

    assert (["note", "note--yours", "note--vetoed"], "Mine.", f"vetoed by ada {EYE}") in shown


def test_the_viewers_own_seen_it_is_on_the_line_for_a_closed_card_and_off_it_for_an_open_one(marked):
    mark(marked["ada"], marked["film"], seen=True)

    card = pool_card(marked["client"].get("/").text, marked["film"])

    assert '<p class="seers seers--yours">' in card
    assert '<span class="seers__all">ada, Fen, Gus</span><span class="seers__others">Fen, Gus</span>' in card


def test_a_line_of_the_viewers_own_seen_it_alone_is_flagged_so_an_open_card_hides_it(everyone):
    alone = film(everyone["Hanna"], "Alone", Approval.APPROVED)
    mark(everyone["ada"], alone, seen=True)

    card = pool_card(signed_in(everyone["ada"]).get("/").text, alone)

    assert lines(card)[-1][0] == ["note", "note--seers", "note--yours"]


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE])
@pytest.mark.parametrize("toggle, expected", [("veto", "Vetoed by ada"), ("seen", "Seen by ada")])
def test_a_save_with_a_veto_or_seen_it_closes_the_card_listing_the_mark(everyone, phase, toggle, expected):
    walk_to(phase)
    each = film(everyone["Hanna"], "One", Approval.UNDECIDED)

    answer = save(signed_in(everyone["ada"]), everyone["ada"], each, **{toggle: True}, headers=HTMX).text

    assert f'<ul class="film-card__notes" id="notes-{each.pk}">' in answer and 'class="film-card"' in answer
    assert expected in lines(answer)[-1][2]


def test_a_veto_taken_back_by_a_save_leaves_the_card_unmarked(marked):
    mark(marked["ada"], marked["film"], vetoed=True)
    save(signed_in(marked["ada"]), marked["ada"], marked["film"], veto=False, headers=HTMX)

    assert "Vetoed by ada" not in marked["client"].get("/").text


def make_films(everyone, count, start=0):
    for each in range(start, start + count):
        suggestion = film(everyone["Hanna"], f"Film {each}", Approval.APPROVED)
        Note.objects.create(suggestion=suggestion, author=everyone["Hanna"], text="Pitch.")
        mark(everyone["Dani"], suggestion, vetoed=True, seen=True)
        mark(everyone["Cleo"], suggestion, seen=True)
        mark(everyone["Bram"], suggestion, vetoed=True)


def queries(client, path):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(path).status_code == 200
    return len(captured)


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE])
def test_the_pool_loads_every_cards_marks_in_as_many_queries_however_many_films_and_records(everyone, phase):
    walk_to(phase)
    client = signed_in(everyone["ada"])
    make_films(everyone, 1)
    small = queries(client, "/")

    make_films(everyone, 5, start=1)

    assert queries(client, "/") == small


def test_the_films_tab_loads_every_rows_marks_in_as_many_queries_however_many_films_and_records(everyone, admin):
    walk_to(Phase.APPROVE)
    make_films(everyone, 1)
    small = queries(admin, TAB)

    make_films(everyone, 5, start=1)

    assert queries(admin, TAB) == small


def cells(page):
    """Each row's marks cell as (title of each part, text), by film title."""
    found = {}
    for title, body in re.findall(r'<td class="films-ledger__film"><button[^>]*>([^<]+)</button>.*?<td class="films-ledger__marks">(.*?)</td>', page, re.S):
        found[html.unescape(title)] = (re.findall(r'title="([^"]*)"', body), " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)).split()))
    return found


def test_the_films_tab_cell_gives_each_count_and_names_the_voters_on_hover(marked, admin):
    walk_to(Phase.APPROVE)

    titles, shown = cells(admin.get(TAB).text)["One"]

    assert shown == f"☒ 3 · {EYE} 5"
    assert titles == ["Vetoed by Bram, Cleo, Dani", "Seen by Bram, Dani, Fen, Gus, Hanna"]


def test_a_part_shows_only_when_it_is_not_zero_and_the_cell_is_blank_when_both_are(everyone, admin):
    walk_to(Phase.APPROVE)
    only_vetoed, only_seen = film(everyone["Hanna"], "Vetoed", Approval.UNDECIDED), film(everyone["Hanna"], "Seen", Approval.UNDECIDED)
    film(everyone["Hanna"], "Neither", Approval.UNDECIDED)
    mark(everyone["Dani"], only_vetoed, vetoed=True)
    mark(everyone["Dani"], only_seen, seen=True)

    shown = cells(admin.get(TAB).text)

    assert shown["Vetoed"] == (["Vetoed by Dani"], "☒ 1")
    assert shown["Seen"] == (["Seen by Dani"], f"{EYE} 1")
    assert shown["Neither"] == ([], "")


@pytest.mark.parametrize("approval", [Approval.UNDECIDED, Approval.APPROVED, Approval.DROPPED])
def test_the_counts_are_over_every_voters_records_whatever_the_films_approval(everyone, admin, approval):
    walk_to(Phase.APPROVE)
    each = film(everyone["Hanna"], "Any", approval)
    mark(everyone["Dani"], each, vetoed=True, seen=True)
    mark(everyone["ada"], each, seen=True)

    assert cells(admin.get(TAB).text)["Any"][1] == f"☒ 1 · {EYE} 2"


def test_a_vetoers_bare_line_is_no_note_on_the_films_tab(marked, admin):
    walk_to(Phase.APPROVE)
    notes = re.search(r'<td class="films-ledger__film">.*?<td class="ledger__number films-ledger__notes">(\d+)</td>', admin.get(TAB).text, re.S)[1]

    assert notes == "2"
