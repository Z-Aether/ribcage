import re

import pytest
from django.test import Client

from ribcage.identity.models import Voter

GALLERY = "/gallery/"


@pytest.fixture
def debug(settings):
    settings.DEBUG = True


@pytest.fixture
def client(client, db):
    # The gallery sits behind the login wall like any page that doesn't opt out (#58, #70).
    client.force_login(Voter.objects.create_voter("Ada"))
    return client


def notes_on_each_card(page):
    cards = re.findall(r'class="film-card__toggle"[^>]*>([^<]+)</button>(.*?)</article>', page, re.S)
    return {title: re.findall(r'<li class="(note[^"]*)"', card) for title, card in cards}


def picker_tiles(page):
    return re.findall(r'<button type="button" class="tile tile--choice.*?</button>', page, re.S)


def dtdd_sections(page):
    """The state of each opened card's DoesTheDogDie section, in the voter skin's own block of the four (#103)."""
    return re.findall(r'<p class="gallery-label">The DoesTheDogDie section: [^<]*</p>\s*<div class="film-cards" data-film-cards>.*?class="film-card__dtdd dtdd dtdd--([a-z-]+)"', page, re.S)


def query_table(sql):
    return re.search(r'FROM "(\w+)"', sql)[1]


def test_the_gallery_does_not_exist_with_debug_off(client, settings):
    assert not settings.DEBUG

    assert client.get(GALLERY).status_code == 404


def test_the_gallery_renders_with_debug_on_and_no_queries_beyond_the_session_voter_phase_and_nag_lookups(
    client, debug, django_assert_num_queries
):
    with django_assert_num_queries(5) as captured:
        response = client.get(GALLERY)

    assert response.status_code == 200
    assert [query_table(query["sql"]) for query in captured.captured_queries] == ["django_session", "identity_voter", "phase_phasemove", "triggers_watchedtopic", "triggers_doesnotcare"]
    # The phase is the header's, read once: the My warnings menu item, and the nag bar, which asks the two lists a voter can decide by (#107, #110).


def test_the_gallery_is_behind_the_login_wall(debug, db):
    assert Client().get(GALLERY).headers["Location"] == f"/login/?next={GALLERY}"


@pytest.mark.parametrize(
    "real_case",
    [
        pytest.param('title-card"><span class="title-card__title">Del Toro', id="a posterless film"),
        pytest.param("Winnie-the-Pooh: Blood and Honey 2", id="a long title"),
        pytest.param("La casa lobo", id="an original title that differs"),
        pytest.param('<span class="runtime__source">by hand</span>', id="a hand-entered runtime"),
        pytest.param(lambda page: len(notes_on_each_card(page)["Midsommar"]) > 3, id="a film with many notes"),
        pytest.param(
            lambda page: notes_on_each_card(page)["Winnie-the-Pooh: Blood and Honey 2"] == ["note note--pitch"],
            id="a film with only a pitch",
        ),
        pytest.param('<span class="removed-tag">removed</span>', id="a removed suggester"),
        pytest.param('<a class="runtime__pencil"', id="the runtime pencil"),
        pytest.param('<p class="runtime__refusal" role="status">', id="the runtime pencil open, refusing"),
        pytest.param("written for the gallery", id="saying the voters and notes are samples"),
        pytest.param(lambda page: "already suggested by Ash" in picker_tiles(page)[0], id="the picker's already suggested tile"),
        pytest.param(lambda page: 'title-card"><span class="title-card__title">Insidious' in picker_tiles(page)[-1], id="the picker's title-card tile"),
        pytest.param("answering right now. Try again in a bit", id="the picker's outage message"),
        pytest.param(
            lambda page: dtdd_sections(page) == ["matched", "uncovered", "not-fetched", "no-match"], id="the dtdd section in its four states"
        ),
        pytest.param(lambda page: "<details class=\"dtdd__topics\">" in page, id="the dtdd topic list behind its control"),
        pytest.param('<span class="dtdd__set-by">set by Dani</span>', id="a match set by someone"),
        pytest.param('<summary class="dtdd__wrong">Wrong film?</summary>', id="the match correction's collapsed control"),
        pytest.param('<p class="dtdd__preview"><span class="film-card__label">Found:</span>', id="a correction's preview"),
        pytest.param('<p class="dtdd__refusal" id="dtdd-refusal-" role="status">', id="a correction's refused link"),
    ],
)
def test_the_gallery_shows_each_real_case(client, debug, real_case):
    page = client.get(GALLERY).content.decode()

    assert real_case(page) if callable(real_case) else real_case in page


def test_the_gallery_shows_every_skin(client, debug):
    page = client.get(GALLERY).content.decode()

    for skin in ("voter", "admin", "run"):
        assert f'data-skin="{skin}"' in page


def test_the_gallery_shows_both_phase_bars_on_opened_cards(client, debug):
    page = client.get(GALLERY).content.decode()

    opened = [card for card in re.findall(r"<article.*?</article>", page, re.S) if 'class="film-card is-open"' in card]
    for bar in ("phase-bar--suggest", "phase-bar--approve"):
        assert any(f'class="phase-bar {bar}"' in card for card in opened)
    assert "Your pitch" in page and "Your note" in page


def vote_cards(page):
    return [card for card in re.findall(r"<article.*?</article>", page, re.S) if "data-vote-bar" in card]


def test_the_gallery_shows_votes_bar_on_opened_cards_with_a_veto_and_the_seen_it_line(client, debug):
    cards = vote_cards(client.get(GALLERY).content.decode())

    bars = [re.search(r'<div class="film-card__phase-bar" data-phase-bar>(.*)</div>\s*(?:<section|$)', card, re.S)[1] for card in cards]
    assert len(bars) == 3 and "hx-post" not in "".join(bars)
    assert "score--keen is-current" in bars[0] and "Seen by" in bars[0]
    # The bar no longer names the vetoers: the card's notes do (#128).
    assert not any("Vetoed by" in bar for bar in bars)
    for bar in bars:
        row = re.search(r'class="vote-bar__scores".*?\n  </div>', bar, re.S)[0]
        assert row.index("vote-bar__veto") < row.index('class="vote-seen"')
    assert "is-vetoed" in bars[1] and "−2" in bars[1] and "data-vote-reason" in bars[1] and "checked" in bars[1]


def test_the_gallery_shows_a_marked_note_a_bare_veto_line_and_the_boxes_quiet_line(client, debug):
    cards = vote_cards(client.get(GALLERY).content.decode())

    assert re.search(r'<li class="note note--vetoed">.*?<span class="note__author">vetoed by Ash</span>', cards[0], re.S)
    assert re.search(r'<li class="note note--vetoed note--bare"><span class="note__author">Vetoed by Zoë</span></li>', cards[0])
    assert "Your note on this film shows as your veto reason, and stays your note if you take the veto back." in cards[1]
    assert "Subtitled, so not the last film of the night.</textarea>" in cards[1]
    assert "Your pitch shows as your veto reason" in cards[2] and "is-refusal" in cards[2]


def test_the_gallery_shows_withdraw_on_an_opened_card_and_armed_on_another(client, debug):
    page = client.get(GALLERY).content.decode()

    opened = [card for card in re.findall(r"<article.*?</article>", page, re.S) if 'class="film-card is-open"' in card]
    withdraws = [re.search(r'<div class="withdraw([^"]*)" data-withdraw>', card) for card in opened]
    assert sorted(found[1] for found in withdraws if found) == ["", " is-armed"]
    assert "V/H/S/99 leaves the pool, and takes your pitch and 2 notes from the group with it." in re.sub(r"<[^>]+>", "", page)


def test_the_gallery_shows_the_password_confirmation(client, debug):
    page = client.get(GALLERY).content.decode()

    assert 'data-confirms-password="gallery_password"' in page


def test_the_gallerys_picker_tiles_lead_nowhere(client, debug):
    # The gallery has no step to swap in, so a tile there must fire no request (#93).
    tiles = picker_tiles(client.get(GALLERY).content.decode())

    assert tiles and not any("hx-get" in tile for tile in tiles)


def test_the_gallerys_pickers_hold_no_link_that_fires_a_request(client, debug):
    # The gallery has no #picker to swap into, so the by-hand offers there are inert (#94).
    page = client.get(GALLERY).content.decode()

    assert "add it by hand" in page
    assert "by_hand=1" not in page


def test_the_gallerys_match_corrections_submit_nothing_and_take_no_focus(client, debug):
    # The gallery has no film to correct, so its control, preview and refusal are inert: no form submits, by click or Enter (#105).
    page = client.get(GALLERY).content.decode()
    controls = re.findall(r'<div class="dtdd__matching.*?</div>', page, re.S)
    forms = [form for control in controls for form in re.findall(r"<form[^>]*>", control)]

    assert controls and not any(re.search(r"hx-(get|post|preserve)|autofocus|action=|href=\"/", control) for control in controls)
    assert forms and all('onsubmit="return false"' in form for form in forms)


def test_the_gallery_lists_no_topic_without_a_yes_vote(client, debug):
    # A real card lists none, so a sample row with 0 yes shows what no card can (#103).
    page = client.get(GALLERY).content.decode()

    assert re.findall(r'class="dtdd__counts">0 yes', page) == []


def test_the_gallery_rings_a_collapsed_and_an_opened_card_and_shows_the_matched_block_and_a_thin_match_without_a_ring(debug, client):
    page = client.get(GALLERY).text
    found = re.findall(r'(<article class="film-card( is-open)?".*?</article>)', page, re.S)
    ringed = {}
    for each, opened in found:
        # The first of each film is the card list's own; later ones are the sections that follow.
        ringed.setdefault(re.search(r'film-card__toggle"[^>]*>([^<]+)<', each)[1], ("has-trigger-icon" in each, bool(opened)))

    assert ringed["Midsommar"] == (True, True)
    assert ringed["The Wolf House"] == (True, False)
    assert ringed["V/H/S/99"][0] is False
    assert page.count('<div class="dtdd__matched">') >= 3


def test_the_gallery_shows_the_watch_toggles_on_an_opened_list_with_the_watched_rows_pressed(debug, client):
    page = client.get(GALLERY).text
    opened = re.search(r'The watch toggles: .*?(<details class="dtdd__topics" open.*?</details>)', page, re.S)[1]

    assert re.findall(r'aria-pressed="(\w+)" aria-label="[^"]*(?:blood or gore|jump scares|body horror)"', opened) == ["true", "false", "true"]
    # Inert, as the other samples' controls are: no route to post to (#114).
    assert 'hx-post="' not in opened and 'onsubmit="return false"' in opened


def test_the_gallery_matched_blocks_and_rings_agree_with_the_watched_rows(debug, client):
    from ribcage.gallery import samples
    from ribcage.triggers.carrying import carries

    for sample in samples.cards():
        rows = [row for group in sample.dtdd.groups for row in group.rows if row.topic_id in samples.WATCHING.ticked and row.yes]
        listed = sample.matched.rows if sample.matched else ()
        assert {row.label for row in listed} == {row.label for row in rows}
        assert (sample.matched.ring if sample.matched else False) == any(carries(row) for row in rows)


def test_the_gallery_shows_the_ballots_tray_and_bands_and_posts_nowhere(client, debug):
    page = client.get(GALLERY).text

    assert re.findall(r'data-place="(-?\w+)"', page) == ["unsorted", "3", "2", "1", "0", "-1", "veto"]
    assert "data-places-at" not in page
    assert "tray" in page and page.count('class="band band--') == 6



def test_the_gallerys_veto_band_has_a_row_with_matched_topics_and_credit_and_one_without_and_saves_nowhere(client, debug):
    band = re.search(r'<section class="band band--veto".*?</section>', client.get(GALLERY).text, re.S)[0]
    rows = re.findall(r'<li class="veto-row".*?</div>\s*</li>', band, re.S)

    assert len(rows) == 2
    assert "On your list" in rows[0] and "Powered by DoesTheDogDie.com" in rows[0] and "veto-ribbon" in rows[0]
    assert "On your list" not in rows[1] and "Powered by" not in rows[1]
    assert all(" disabled>Save" in row for row in rows)


def test_the_gallerys_seen_it_toggles_show_off_and_on_and_fire_no_request(client, debug):
    # The gallery posts nothing, so its toggles only flip the tile's look (#121).
    page = client.get(GALLERY).content.decode()
    toggles = re.findall(r'<button type="button" class="seen-toggle.*?</button>', page, re.S)

    assert any('aria-pressed="true"' in toggle for toggle in toggles) and any('aria-pressed="false"' in toggle for toggle in toggles)
    assert not any("hx-post" in toggle for toggle in toggles)
    assert 'class="ballot-legend"' in page


def test_the_gallerys_done_block_shows_im_done_off_and_on_over_the_roster_and_posts_nowhere(client, debug):
    page = client.get(GALLERY).content.decode()
    blocks = re.findall(r'<div class="ballot-done".*?</ul></div>', page, re.S)

    assert len(blocks) == 2
    assert 'aria-pressed="false"' in blocks[0] and 'aria-pressed="true"' in blocks[1]
    assert all("hx-post" not in block and "<form class=\"ballot-done__toggle\">" in block for block in blocks)
    assert all("2 of 6 done" in block or "3 of 6 done" in block for block in blocks)
