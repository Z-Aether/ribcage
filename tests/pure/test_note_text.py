"""What a saved note's text is, before anything is stored: trimmed, one kind of line break, and never cut (#88)."""

import pytest

from ribcage.suggestions.notes import TooLong, note_text


def test_the_text_is_trimmed():
    assert note_text("  I'm in.\n") == "I'm in."


def test_whitespace_alone_is_an_empty_note():
    assert note_text(" \r\n\t ") == ""


def test_a_browsers_line_breaks_are_kept_as_one_character_each():
    assert note_text("First line.\r\nSecond line.") == "First line.\nSecond line."


def test_a_note_at_the_cap_is_kept_whole(settings):
    settings.NOTE_MAX_LENGTH = 10

    assert note_text("a" * 10) == "a" * 10


def test_a_note_over_the_cap_is_refused_with_its_length_never_cut(settings):
    settings.NOTE_MAX_LENGTH = 10

    with pytest.raises(TooLong) as refused:
        note_text("  " + "a" * 11 + "  ")

    assert (refused.value.length, refused.value.cap) == (11, 10)


def test_the_cap_counts_a_line_break_once(settings):
    settings.NOTE_MAX_LENGTH = 3

    assert note_text("a\r\nb") == "a\nb"
