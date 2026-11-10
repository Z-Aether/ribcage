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


def picker_tiles(page):
    return re.findall(r'<button type="button" class="tile tile--choice.*?</button>', page, re.S)


def test_the_gallery_does_not_exist_with_debug_off(client, settings):
    assert not settings.DEBUG

    assert client.get(GALLERY).status_code == 404


def test_the_gallery_renders_with_debug_on(client, debug):
    assert client.get(GALLERY).status_code == 200


def test_the_gallery_is_behind_the_login_wall(debug, db):
    assert Client().get(GALLERY).headers["Location"] == f"/login/?next={GALLERY}"


def test_the_gallerys_suggest_and_approve_bars_post_nowhere(client, debug):
    page = client.get(GALLERY).content.decode()

    opened = [card for card in re.findall(r"<article.*?</article>", page, re.S) if 'class="film-card is-open"' in card]
    for bar in ("phase-bar--suggest", "phase-bar--approve"):
        cards = [card for card in opened if f'class="phase-bar {bar}"' in card]
        assert cards and not any('hx-post="/ballot/' in card for card in cards)


def vote_cards(page):
    return [card for card in re.findall(r"<article.*?</article>", page, re.S) if "data-vote-bar" in card]


def test_the_gallerys_vote_bars_post_nowhere(client, debug):
    cards = vote_cards(client.get(GALLERY).content.decode())

    # The note box posts with no suggestion, so a save only reloads; the pills and seen it post nowhere (#150).
    assert cards and not any('hx-post="/ballot/' in card for card in cards)


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


def test_the_gallerys_watch_toggles_post_nowhere(debug, client):
    page = client.get(GALLERY).text
    opened = re.search(r'The watch toggles: .*?(<details class="dtdd__topics" open.*?</details>)', page, re.S)[1]

    # Inert, as the other samples' controls are: no route to post to (#114).
    assert 'hx-post="' not in opened and 'onsubmit="return false"' in opened


def test_the_gallerys_ballot_board_posts_nowhere(client, debug):
    page = client.get(GALLERY).text

    assert "data-board" in page and "data-places-at" not in page


def test_the_gallerys_seen_it_toggles_fire_no_request(client, debug):
    # The gallery posts nothing, so its toggles only flip the tile's look (#121).
    page = client.get(GALLERY).content.decode()
    toggles = re.findall(r'<button type="button" class="seen-toggle.*?</button>', page, re.S)

    assert toggles and not any("hx-post" in toggle for toggle in toggles)


def test_the_gallerys_done_blocks_post_nowhere(client, debug):
    page = client.get(GALLERY).content.decode()
    blocks = re.findall(r'<div class="ballot-done".*?</ul></div>', page, re.S)

    assert blocks and all("hx-post" not in block and '<form class="ballot-done__toggle">' in block for block in blocks)


def test_no_card_opens_from_the_gallerys_sample_matrix(client, debug):
    page = client.get(GALLERY).text

    # The sample matrix is a picture: no card opens from it.
    assert 'class="reveal__matrix"' in page and "data-reveal" not in page and "reveal-card" not in page


def test_the_gallerys_slate_ledger_keeps_and_discards_nothing(client, debug):
    page = client.get(GALLERY).text
    section = re.search(r'id="slate-ledger".*?</section>', page, re.S)[0]

    assert "data-keep" in section and "data-discard" in section
    assert "<form" not in section
    assert "pick/keep" not in section and "pick/discard" not in section


def test_the_gallerys_slate_ledger_ticks_do_nothing(client, debug):
    page = client.get(GALLERY).text
    section = re.search(r'id="slate-ledger".*?</section>', page, re.S)[0]

    ticks = re.findall(r"<input[^>]*data-swap-tick[^>]*>", section)

    assert ticks and all(" disabled" in each for each in ticks)
    assert 'id="swap-panel"' not in section
