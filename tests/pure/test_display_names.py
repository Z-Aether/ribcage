import pytest
from django.core.exceptions import ValidationError

from ribcage.identity import display_names


@pytest.mark.parametrize(
    ("typed", "normalised"),
    [
        ("  Sam  ", "Sam"),
        ("Anne   Marie", "Anne Marie"),
        ("Anne\t\n Marie", "Anne Marie"),
        ("Anne Marie", "Anne Marie"),
        ("Anne Marie", "Anne Marie"),
        ("Anne Marie", "Anne Marie"),
        ("Ｓam", "Sam"),
        ("ﬁnn", "finn"),
        ("Sam", "Sam"),
    ],
)
def test_normalising(typed, normalised):
    assert display_names.normalise(typed) == normalised


def test_case_is_kept_as_typed():
    assert display_names.clean("sAM") == "sAM"


@pytest.mark.parametrize("accepted", ["S", "O'Brien", "Anne-Marie", "🎬", "Zoë", "a" * 20, "🎬" * 20])
def test_accepted(accepted):
    assert display_names.clean(accepted) == accepted


@pytest.mark.parametrize("refused", ["", "   ", "a" * 21, "🎬" * 21])
def test_length_is_one_to_twenty(refused):
    with pytest.raises(ValidationError):
        display_names.clean(refused)


@pytest.mark.parametrize("character", ["\x00", "\x07", "\x7f", "\u200b", "\u200d", "\ufeff", "\u202e"])
def test_control_and_zero_width_characters_refused(character):
    with pytest.raises(ValidationError):
        display_names.clean(f"Sa{character}m")


def test_length_counts_after_normalising():
    assert display_names.clean("  " + "a" * 20 + "  ") == "a" * 20
    assert display_names.clean("a" * 10 + "          " + "b" * 9) == "a" * 10 + " " + "b" * 9
