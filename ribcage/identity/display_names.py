import unicodedata

from django.core.exceptions import ValidationError

MAX_LENGTH = 20
# Control, format, surrogate, private-use and unassigned. Format includes U+200D, so ZWJ emoji sequences are refused on
# purpose: the simpler rule also stops invisible lookalikes such as Sa<ZWJ>m (#69).
REFUSED_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn"}


def normalise(display_name):
    folded = unicodedata.normalize("NFKC", display_name)
    return " ".join(folded.split())


def key(display_name):
    """The case-blind form two names are compared by, for every language's letters, not only A-Z (#69)."""
    return normalise(display_name).casefold()


def validate(display_name):
    """Check an already normalised display name against #37's rules."""
    if not display_name:
        raise ValidationError("Choose a display name.", code="empty")
    if len(display_name) > MAX_LENGTH:
        raise ValidationError(f"A display name is at most {MAX_LENGTH} characters.", code="too_long")
    if any(unicodedata.category(character) in REFUSED_CATEGORIES for character in display_name):
        raise ValidationError("A display name can't contain invisible or control characters, which includes the joiner inside some emoji.", code="unprintable")


def clean(display_name):
    normalised = normalise(display_name)
    validate(normalised)
    return normalised
