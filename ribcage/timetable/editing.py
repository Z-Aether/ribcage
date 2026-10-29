"""The timetable's one edit: a change to one box under a ripple mode, previewed or saved by the same call (#22, #139).

`run` loads the boxes, has `engine.edit` return them after the change and, only when told to save, stores what differs. A preview
and a save of the same values therefore show and store exactly the same boxes, and the save is the server's however slow the
preview ran. #141's mode, #142's and #143's resizes and #144's insert add a change or a mode to the engine and a line to `stored`, not a new call.
"""

from dataclasses import replace

from django.db import transaction

from ribcage.suggestions import runtime
from ribcage.suggestions.models import Suggestion
from ribcage.timetable import engine, track
from ribcage.timetable.models import Box

# Far enough for any evening; a start outside it is a tampered post, not a drag.
FURTHEST = 100_000


def valid_start(typed):
    """A whole number of elapsed minutes within reach, or None."""
    try:
        start = int(typed)
    except (TypeError, ValueError):
        return None
    return start if abs(start) <= FURTHEST and str(typed).strip().lstrip("-+").isdigit() else None


def run(box_id, change, mode, save):
    """The track's boxes after the change, stored when `save`; None where the box is gone, so the caller reloads the tab."""
    with transaction.atomic():
        before = track.stored_boxes()
        if not any(each.key == box_id for each in before):
            return None
        placed = [engine.Placed(each.key, each.start, each.length, each.film is not None, each.flexible) for each in before]
        after = {each.key: each for each in engine.edit(placed, box_id, change, mode)}
        boxes = [replace(each, start=after[each.key].start, length=after[each.key].length) for each in before]
        if save:
            stored(before, boxes)
    return boxes


def stored(before, after):
    """Write what changed: a box's start, a labelled box's length and a film's runtime, which every card and SOLVE read (#142)."""
    for each, new in zip(before, after, strict=True):
        if each.start != new.start:
            Box.objects.filter(pk=each.key).update(start=new.start)
        if each.length != new.length and each.film is None:
            Box.objects.filter(pk=each.key, suggestion__isnull=True).update(length=new.length)
        elif each.length != new.length:
            # The film's own runtime, so the source then reads by hand, or TMDB again once corrected back (#21, #142).
            runtime.correct(Suggestion.objects.get(box=each.key), str(new.length))
