"""Removal keeps a voter's suggestions and pitches, marked removed, and deletes their notes on other films (#26 §2, #28, #98)."""

import html
import re

import pytest
from django.test import Client

from ribcage.identity.removal import remove
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Note, Suggestion
from tests.films import a_tmdb_film
from tests.http.test_pool import walk_to
from tests.http.test_registration import register
from tests.http.test_roster_tab import TAB, confirm, text

REMOVE = "/console/roster/remove/"
POOL_PHASES = [Phase.SUGGEST, Phase.APPROVE]


@pytest.fixture
def pool(voters):
    # Ada suggests two films and notes Hanna's; Hanna suggests one and notes one of Ada's; Dani only writes notes.
    ada, hanna, dani = voters["ada"], voters["Hanna"], voters["Dani"]
    thing = Suggestion.objects.suggest(ada, a_tmdb_film(1091, "The Thing"), "Ada pitches The Thing.")
    cube = Suggestion.objects.suggest(ada, a_tmdb_film(431, "Cube"), "Ada pitches Cube.")
    shining = Suggestion.objects.suggest(hanna, a_tmdb_film(694, "The Shining"), "Hanna pitches The Shining.")
    thing.notes.create(author=hanna, text="Hanna on The Thing.")
    thing.notes.create(author=dani, text="Dani on The Thing.")
    shining.notes.create(author=ada, text="Ada on The Shining.")
    return {"thing": thing, "cube": cube, "shining": shining}


def goes(page):
    return [text(item) for item in re.findall(r'<li class="roster-confirm__goes">(.*?)</li>', page, re.S)]


def voter_page(voter):
    browser = Client()
    browser.force_login(voter)
    return browser.get("/").text


def test_the_voters_notes_on_other_films_are_gone_and_nothing_else_of_anyones(admin, voters, pool):
    admin.post(REMOVE, {"voter": voters["ada"].pk})

    assert sorted(Note.objects.values_list("text", flat=True)) == [
        "Ada pitches Cube.",
        "Ada pitches The Thing.",
        "Dani on The Thing.",
        "Hanna on The Thing.",
        "Hanna pitches The Shining.",
    ]


def test_their_suggestions_and_pitches_remain_with_no_other_note_left_blank(admin, voters, pool):
    admin.post(REMOVE, {"voter": voters["ada"].pk})

    assert sorted(Suggestion.objects.filter(suggester=None).values_list("suggester_name", flat=True)) == ["ada", "ada"]
    blank = Note.objects.filter(author=None)
    assert sorted(blank.values_list("text", flat=True)) == ["Ada pitches Cube.", "Ada pitches The Thing."]
    assert all(note.author_id == note.suggestion.suggester_id for note in blank)


@pytest.mark.parametrize("phase", POOL_PHASES)
def test_the_pool_shows_their_cards_marked_removed_with_pitches_and_without_their_notes(admin, voters, pool, phase):
    walk_to(phase)
    admin.post(REMOVE, {"voter": voters["ada"].pk})

    page = voter_page(voters["Dani"])

    assert page.count('<span class="film-card__suggester is-removed">ada</span> <span class="removed-tag">removed</span>') == 2
    assert "Ada pitches The Thing." in page and "Ada pitches Cube." in page
    assert "Ada on The Shining." not in page
    assert "Hanna on The Thing." in page


def test_a_voter_who_rejoins_under_the_same_name_owns_none_of_it(admin, voters, pool):
    walk_to(Phase.SUGGEST)
    admin.post(REMOVE, {"voter": voters["ada"].pk})
    again = Client()
    register(again, "ada")

    page = again.get("/").text
    again.post("/withdraw/", {"suggestion": pool["thing"].pk}, headers={"HX-Request": "true"})

    assert "Ada pitches The Thing." in page
    assert "withdraw__act" not in page
    assert '<textarea name="text" rows="3">Ada pitches' not in page
    assert "Your pitch" not in page
    assert Suggestion.objects.get(pk=pool["thing"].pk).suggester_id is None
    assert Suggestion.objects.filter(pk=pool["thing"].pk).exists()


def test_the_confirm_lists_the_counts_of_notes_and_suggestions(admin, voters, pool):
    page = admin.get(TAB, {"remove": voters["ada"].pk}).text

    assert goes(page)[2:-1] == ["their one note on another film", "their 2 suggestions stay, with their pitches, marked removed"]
    assert confirm(page) is not None


def test_the_confirm_leaves_out_what_the_voter_does_not_have(admin, voters, pool):
    dani = goes(admin.get(TAB, {"remove": voters["Dani"].pk}).text)

    assert dani[2:-1] == ["their one note on another film"]
    hanna = goes(admin.get(TAB, {"remove": voters["Hanna"].pk}).text)
    assert hanna[2:-1] == ["their one note on another film", "their suggestion stays, with its pitch, marked removed"]
    remove(voters["Dani"])
    nothing = goes(admin.get(TAB, {"remove": voters["Hanna"].pk}).text)
    assert nothing[2:-1] == hanna[2:-1]
    Note.objects.filter(author=voters["Hanna"]).delete()
    assert goes(admin.get(TAB, {"remove": voters["Hanna"].pk}).text)[2:-1] == ["their suggestion stays, with its pitch, marked removed"]
    Suggestion.objects.filter(suggester=voters["Hanna"]).delete()
    assert len(goes(admin.get(TAB, {"remove": voters["Hanna"].pk}).text)) == 3


def test_the_withdraw_count_takes_every_note_but_the_pitch(admin, voters, pool):
    walk_to(Phase.SUGGEST)
    admin.post(REMOVE, {"voter": voters["Dani"].pk})
    browser = Client()
    browser.force_login(voters["ada"])

    page = html.unescape(browser.get("/withdraw/", {"suggestion": pool["thing"].pk}, headers={"HX-Request": "true"}).text)

    assert "takes your pitch and one note from the group with it" in text(page)
