"""The voter header keeps the marathon's words whole and lets the menu give way first (#129)."""

import re
from pathlib import Path

import ribcage

CSS = (Path(ribcage.__file__).parent / "static" / "theme" / "theme.css").read_text(encoding="utf-8")


def rule(selector):
    return re.search(re.escape(selector) + r" \{(.*?)\}", CSS, re.DOTALL).group(1)


def test_the_wordmark_breaks_only_between_words_unless_one_word_overflows():
    body = rule("[data-skin] .voter-header__wordmark")

    assert "overflow-wrap: break-word" in body
    assert "flex: 0 100 auto" in body
    assert "min-width" not in body


def test_the_menu_shrinks_and_keeps_names_whole_where_it_can():
    assert "flex: 0 1 auto" in rule("[data-skin] details.voter-menu")
    assert "overflow-wrap: break-word" in rule("[data-skin] .voter-menu > summary.voter-menu__name")


def test_the_menu_has_a_short_floor_under_its_cap_and_the_caret_cannot_wrap():
    menu = rule("[data-skin] details.voter-menu")
    caret = rule("[data-skin] .voter-menu > summary.voter-menu__name::after")

    assert "min-width: 5.5rem" in menu
    assert "min-width: min-content" not in menu
    assert "max-width: 55%" in menu
    assert "position: absolute" in caret
