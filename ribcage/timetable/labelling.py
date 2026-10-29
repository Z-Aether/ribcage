"""The one write of a labelled box's label and length together, refused whole and gently (#22, #138).

#140 later sends the length through the ripple mode; it replaces `save`'s plain update and keeps its refusals.
"""

from dataclasses import dataclass

from ribcage.suggestions import runtime
from ribcage.timetable.models import LABEL_LENGTH, SMALLEST_LABELLED_LENGTH, Box

STEP = 5
NO_LABEL = "The label is empty. Type what the box is, like Dinner."
LONG_LABEL = f"A label is at most {LABEL_LENGTH} characters. Shorten it."
EMPTY = "The length is empty. Type it in minutes, like 30."
NOT_WHOLE_MINUTES = "A length is whole minutes, like 30. Type it that way."
TOO_SHORT = f"A box is at least {SMALLEST_LABELLED_LENGTH} minutes long. Check the number."
NOT_IN_STEPS = f"A length goes in steps of {STEP} minutes, like 25 or 30. Check the number."
TOO_LONG = "No box runs that long. Check the number."


@dataclass(frozen=True)
class Refused:
    """A panel save refused: what was typed, kept in its boxes, and what to say beside each (None where fine)."""

    label: str
    length: str
    says_label: str | None
    says_length: str | None


# The runtime parser's refusals, in the box's own words (#138).
IN_BOXS_WORDS = {
    runtime.EMPTY: EMPTY,
    runtime.NOT_WHOLE_MINUTES: NOT_WHOLE_MINUTES,
    runtime.NOT_POSITIVE: TOO_SHORT,
    runtime.TOO_LONG: TOO_LONG,
}


def length_refusal(typed):
    """The gentle word for a length that isn't whole minutes in steps of 5 and at least 5, or None."""
    try:
        value = runtime.minutes(typed)
    except runtime.Refused as refused:
        return IN_BOXS_WORDS[str(refused)]
    if value < SMALLEST_LABELLED_LENGTH:
        return TOO_SHORT
    return None if value % STEP == 0 else NOT_IN_STEPS


def save(box_id, label, length):
    """Save a labelled box's label and length together, or return a Refused and save nothing; a box gone or a film's changes nothing."""
    says_label = NO_LABEL if not label.strip() else LONG_LABEL if len(label.strip()) > LABEL_LENGTH else None
    says_length = length_refusal(length)
    if says_label or says_length:
        return Refused(label, length, says_label, says_length)
    try:
        Box.objects.filter(pk=box_id, suggestion__isnull=True).update(label=label.strip(), length=int(length.strip()))
    except (TypeError, ValueError):
        pass
    return None
