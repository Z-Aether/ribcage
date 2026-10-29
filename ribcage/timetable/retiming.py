"""The one write of a film box's runtime from the track: an edit like any other, through the ripple mode (#22, #142).

The runtime and any boxes it pushes are written in one transaction, or neither is.
"""

from dataclasses import dataclass

from ribcage.console.films import HELD
from ribcage.suggestions import runtime
from ribcage.timetable import editing, engine
from ribcage.timetable.models import Box


@dataclass(frozen=True)
class Refused:
    """A runtime save refused: what was typed, kept in its box, and why."""

    typed: str
    says: str


def refusal(typed):
    """The gentle word for a runtime the box can't hold, or None; an empty one is the held film's (#97)."""
    if not typed.strip():
        return HELD
    try:
        runtime.minutes(typed)
    except runtime.Refused as refused:
        return str(refused)
    return None


def save(box_id, typed, mode=engine.NONE):
    """Save the film box's runtime as typed, or return a Refused and save nothing; a box gone or a labelled one's changes nothing."""
    if says := refusal(typed):
        return Refused(typed, says)
    try:
        if Box.objects.filter(pk=box_id, suggestion__isnull=False).exists():
            editing.run(int(box_id), engine.Resize(runtime.minutes(typed)), mode, save=True)
    except (TypeError, ValueError):
        pass
    return None
