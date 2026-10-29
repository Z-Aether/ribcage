"""The writes that put a box on the timetable and take one off: the one rule for where a new box lands (#12, #137).

A new box lands flush after the last one, on the 5-minute grid, and never clashes, so no ripple mode applies. Taking a box off
leaves its minutes empty and moves nothing else.
"""

from django.db import IntegrityError, transaction

from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable import setting
from ribcage.timetable.models import Box

GRID = 5
BREAK = "Break"
BREAK_LENGTH = 30


def next_start():
    """Where the next box starts: the last end rounded up to the grid, or the anchor (minute 0) on an empty timetable."""
    ends = [box.start + (box.length if box.suggestion_id is None else box.suggestion.runtime) for box in Box.objects.select_related("suggestion")]
    if not ends:
        return 0
    return -(-max(ends) // GRID) * GRID


def placeable(suggestion_id):
    """The approved film that can be placed now, or None: no anchor, a film already on the timetable, one no longer approved or one gone (#137, #144)."""
    if setting.read().anchor is None:
        return None
    try:
        return Suggestion.objects.filter(pk=suggestion_id, approval=Approval.APPROVED, box__isnull=True).first()
    except (TypeError, ValueError):
        return None


def lay_film(suggestion_id, start=None):
    """Place an approved film's box at `start`, or after the last one, returning the box, or None where nothing changes (#137, #144)."""
    try:
        with transaction.atomic():
            film = placeable(suggestion_id)
            if film is None:
                return None
            return Box.objects.create(suggestion=film, start=next_start() if start is None else start)
    # A second placement of the same film lost the race to the unique key.
    except (IntegrityError, TypeError, ValueError):
        return None


def lay_break():
    """Place a 30-minute *Break* after the last box, returning it, or None with no anchor (#138)."""
    if setting.read().anchor is None:
        return None
    return Box.objects.create(label=BREAK, length=BREAK_LENGTH, start=next_start())


def take_off(box_id):
    """Remove a box, whatever it holds, and move nothing else; False where it was already gone."""
    try:
        return Box.objects.filter(pk=box_id).delete()[0] > 0
    except (TypeError, ValueError):
        return False
