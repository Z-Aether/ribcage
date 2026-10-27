"""A card closes on a click outside it and on Escape (#131). The scripts have no harness, so these hold the shape the browser check found working."""

import re

from django.conf import settings


def script(name):
    return (settings.BASE_DIR / "ribcage/static/components" / name).read_text(encoding="utf-8")


def test_the_pool_closes_an_open_card_on_a_click_outside_it_and_on_escape():
    source = script("film-card.js")

    assert re.search(r"if \(!path\.includes\(open\) && !began\.includes\(open\)\) setOpen\(open, false\)", source)
    assert re.search(r'event\.key !== "Escape"', source)
    assert re.search(r'open\.querySelector\("\.film-card__toggle"\)\.focus\(\)', source)


def test_the_pool_leaves_the_ledger_and_the_ballot_to_their_own_closing():
    source = script("film-card.js")

    assert '.closest(".ledger__detail, [data-board]")' in source


def test_the_ballot_closes_through_the_server_and_keeps_the_typing():
    source = script("ballot-board.js")

    assert re.search(r'close: "1"', source)
    assert re.search(r'event\.key !== "Escape"', source)
    assert "stash(card)" in source and "restore(board)" in source


def test_the_ballot_ignores_clicks_while_a_drag_runs():
    source = script("ballot-board.js")

    assert re.search(r"dragging = true", source)
    assert source.count("dragging ||") + source.count("if (dragging)") >= 2


def test_a_press_that_began_inside_the_card_is_no_outside_click():
    pool = script("film-card.js")
    board = script("ballot-board.js")

    assert re.search(r'addEventListener\("pointerdown", \(event\) => \{\s*pressPath = event\.composedPath\(\);\s*\}, true\)', pool)
    assert re.search(r"!began\.includes\(open\)", pool)
    assert re.search(r'addEventListener\("pointerdown", function \(event\) \{\s*pressPath = event\.composedPath\(\);\s*\}, true\)', board)
    assert "began.includes(card)" in board


def test_the_ballot_ends_a_drag_after_its_pause_and_stashes_before_either_close():
    source = script("ballot-board.js")

    assert re.search(r"setTimeout\(function \(\) \{\s*dragging = false;\s*\}, 50\)", source)
    drop = source.split("onEnd:")[1].split("htmx.ajax")[0]
    opening = source.split("function open(item)")[1].split("htmx.ajax")[0]
    assert "stash(other);" in drop
    assert "stash(other);" in opening


def test_the_ballot_gives_the_typing_back_and_tells_the_page_it_changed():
    source = script("ballot-board.js")
    restore = source.split("function restore(board)")[1].split("function start")[0]

    assert "box.value = text;" in restore
    assert 'box.dispatchEvent(new Event("input", { bubbles: true }))' in restore
