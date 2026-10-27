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


def test_save_waits_for_a_change_and_the_page_loads_the_script():
    source = script("save-waits.js")
    base = (settings.BASE_DIR / "ribcage/templates/base.html").read_text(encoding="utf-8")

    assert "components/save-waits.js" in base
    assert re.search(r"save\.disabled = !\(changed\(form\) \|\| \(fresh && !form\.touched && form\.hasAttribute\(\"data-unsaved\"\)\)\)", source)
    # An input anywhere reads the form it is in, and a settled swap reads the forms it drew (#132).
    assert re.search(r'addEventListener\("input"', source) and re.search(r'addEventListener\("htmx:afterSettle"', source)
    assert re.search(r'addEventListener\("htmx:oobAfterSwap"', source)


def test_a_saved_note_keeps_the_closed_card_in_view():
    source = script("save-waits.js")

    assert re.search(r'addEventListener\("htmx:afterSwap"', source) and 'scrollIntoView({ block: "nearest" })' in source


def test_a_saved_reason_drops_the_films_stashed_typing():
    source = script("ballot-board.js")
    dropping = source.split('addEventListener("htmx:beforeSwap"')[1].split("function start")[0]

    assert 'getResponseHeader("HX-Retarget")' in dropping and "delete typed[" in dropping


def test_the_ballot_stashes_typing_against_the_saved_text_not_the_default():
    source = script("ballot-board.js")
    stashing = source.split("function stash(card)")[1].split("function restore")[0]

    assert "box.dataset.saved" in stashing and "box.defaultValue" not in stashing
    assert stashing.count(r'.replace(/\r\n/g, "\n")') == 2


def test_a_keyboard_save_puts_the_focus_on_the_tile_or_the_title_it_closed_to():
    source = script("save-waits.js")
    beforehand = source.split('"htmx:beforeRequest"')[1].split("\n  });")[0]
    after = source.split("const id = keyboardSave.id;")[1].split("\n  });")[0]

    assert "form.contains(document.activeElement)" in beforehand
    assert "document.activeElement !== document.body" in after
    assert '[data-board] li[data-suggestion="${id}"]:not(.card-item)' in after and "tile.tabIndex = 0" in after
    assert ".film-card__toggle" in after and "preventScroll: true" in after


def test_a_keyboard_save_is_let_go_when_it_fails_and_waits_for_its_own_settle():
    source = script("save-waits.js")
    after = source.split("const id = keyboardSave.id;")[0].split('"htmx:afterSettle"')[1]

    assert 'addEventListener("htmx:responseError", letGo)' in source and 'addEventListener("htmx:sendError", letGo)' in source
    assert "requestConfig.elt !== keyboardSave.form" in after
