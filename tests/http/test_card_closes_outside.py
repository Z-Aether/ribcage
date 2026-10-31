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

    assert "box.value = kept.text;" in restore
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

    assert "document.activeElement.form === form" in beforehand
    assert "document.activeElement" in after
    assert '[data-board] li[data-suggestion="${id}"]:not(.card-item)' in after and "tile.tabIndex = 0" in after
    assert ".film-card__toggle" in after and "preventScroll: true" in after


def test_a_keyboard_save_is_let_go_when_it_fails_and_waits_for_its_own_settle():
    source = script("save-waits.js")
    after = source.split("const id = keyboardSave.id;")[0].split('"htmx:afterSettle"')[1]

    assert 'addEventListener("htmx:responseError", letGo)' in source and 'addEventListener("htmx:sendError", letGo)' in source
    assert "requestConfig.elt !== keyboardSave.form" in after


def test_an_open_runtime_box_counts_as_a_change_even_where_it_sits_outside_the_form():
    source = script("save-waits.js")
    checking = source.split("function changed(form)")[1].split("// A form is fresh")[0]

    # The form's own elements include a box that joins it by its form attribute (#133).
    assert "form.elements" in checking and 'hasAttribute("data-counts-as-change")' in checking
    assert "form.querySelectorAll" not in checking
    assert re.search(r"const form = event\.target\.form;", source)


def test_the_pencil_on_a_closed_pool_card_opens_it_after_the_outside_click_closed_the_rest():
    source = script("film-card.js")
    click = source.split('document.addEventListener("click"')[1].split('document.addEventListener("keydown"')[0]
    opening = re.search(r'if \(card && event\.target\.closest\("\.runtime__pencil"\).*?setOpen\(card, true\);', click, re.S)[0]

    assert click.index("setOpen(open, false)") < click.index(opening)
    assert click.index(opening) < click.index('event.target.closest("a, form")')
    assert '!card.classList.contains("is-open")' in opening and "[data-board]" in opening


def test_a_keyboard_save_sends_the_focus_to_the_title_even_where_htmx_restored_it_inside_the_card():
    source = script("save-waits.js")
    after = source.split("const id = keyboardSave.id;")[1].split("\n  });")[0]

    # The runtime box and the pencil share an id, so htmx moves the focus onto the pencil: that is inside the card, and the title takes it (#89, #132, #133).
    assert "document.activeElement !== document.body" not in after
    assert "(tile || card || document.body).contains(held)" in after
    assert "if (kept) return;" in after


def test_closing_a_card_shuts_a_runtime_box_still_holding_the_stored_runtime_and_keeps_another():
    source = script("film-card.js")
    setting = source.split("function setOpen(card, open)")[1].split("function shutUntouchedBox")[0]
    shutting = source.split("function shutUntouchedBox(card)")[1].split("function setRowOpen")[0]

    assert "if (!open) shutUntouchedBox(card);" in setting
    assert "box.value.trim() !== box.dataset.stored" in shutting.split("\n")[2]
    assert '.runtime__edit").remove()' in shutting and 'classList.remove("is-editing")' in shutting
    # The pencil takes the box's id as the server draws a closed line, and Save is read again without the box (#89, #133).
    assert "pencil.id = id" in shutting and 'new Event("boxes-changed")' in shutting
    assert 'addEventListener("boxes-changed", () => syncAll(document))' in script("save-waits.js")


def test_the_pencil_beside_a_box_left_open_opens_the_card_and_fetches_nothing():
    source = script("film-card.js")
    click = source.split('document.addEventListener("click"')[1].split('document.addEventListener("keydown"')[0]
    fetching = source.split('"htmx:beforeRequest"')[1].split("\n});")[0]

    assert 'card.querySelector(".runtime__edit input")' in click and "left.focus()" in click and "event.preventDefault()" in click
    assert 'matches(".runtime__pencil")' in fetching and 'closest(".is-editing")' in fetching and "event.preventDefault()" in fetching


def test_save_waits_reads_a_toggled_checkbox_against_its_saved_state():
    source = script("save-waits.js")
    differing = source.split("function differs(box)")[1].split("function changed")[0]
    checking = source.split("function changed(form)")[1].split("// A form is fresh")[0]

    # The veto and seen it join the note form and light Save while ticked against what was saved (#152).
    assert 'box.type === "checkbox"' in differing and 'box.checked !== (box.dataset.saved === "1")' in differing
    assert 'hasAttribute("data-saved") && differs(box)' in checking


def test_a_pending_seen_it_is_stashed_against_the_saved_state_and_given_back_with_the_typing():
    source = script("ballot-board.js")
    stashing = source.split("function stash(card)")[1].split("function restore")[0]
    restoring = source.split("function restore(board)")[1].split("function start")[0]

    assert 'seen.checked !== (seen.dataset.saved === "1")' in stashing and "kept.seen = seen.checked" in stashing
    assert "seen.checked = kept.seen;" in restoring and 'seen.dispatchEvent(new Event("input", { bubbles: true }))' in restoring


def test_a_pill_click_stashes_the_card_so_a_pending_seen_it_survives_its_redraw():
    source = script("ballot-board.js")
    pill = source.split('board.addEventListener("htmx:beforeRequest"')[1].split("});")[0]

    assert '.vote-bar__score' in pill and 'stash(pill.closest(".card-item"))' in pill


def test_the_tiles_own_seen_it_drops_a_tick_kept_for_the_film():
    source = script("ballot-board.js")
    toggle = source.split("var refocus = null;")[1].split("document.body.addEventListener")[0]

    assert "delete typed[toggle.closest" in toggle


def test_the_pool_keeps_the_toggles_in_the_page_by_never_resetting_them_on_a_close():
    source = script("film-card.js")
    closing = source.split("function setOpen(card, open)")[1].split("function shutUntouchedBox")[0]

    # Only a runtime box still holding its stored value is shut on a close; the checkboxes stay as toggled (#152).
    assert "checkbox" not in source and "checked" not in source and "shutUntouchedBox(card)" in closing
