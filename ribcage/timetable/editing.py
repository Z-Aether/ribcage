"""The timetable's one edit: a change to one box under a ripple mode, previewed or saved by the same call (#22, #139).

`run` loads the boxes, has `engine.edit` return them after the change and, only when told to save, stores what differs. A preview
and a save of the same values therefore show and store exactly the same boxes, and the save is the server's however slow the
preview ran. #141's mode, #142's and #143's resizes add a change or a mode to the engine and a line to `stored`, not a new call. #144's insert is the one change of a box that is not stored yet, so `insert` loads its film and `stored` creates the box.
"""

from dataclasses import replace

from django.db import transaction

from ribcage.suggestions import runtime
from ribcage.suggestions.models import Suggestion
from ribcage.timetable import engine, laying, setting, track
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


# What the previewed box is called until a save gives it a primary key.
INSERTED = "new"


def insert(suggestion_id, start, mode, save):
    """The track's boxes after laying a candidate film at `start` under a ripple mode, stored when `save`; None where nothing can change.

    Nothing can change with no anchor, for a film already on the timetable, one no longer approved, or one gone: the caller reloads
    the tab as it is (#144, #26 §5). The new box is last, keyed INSERTED, or by its primary key once saved.
    """
    with transaction.atomic():
        film = laying.placeable(suggestion_id)
        if film is None:
            return None
        before = track.stored_boxes()
        placed = [engine.Placed(each.key, each.start, each.length, each.film is not None, each.flexible) for each in before]
        after = {each.key: each for each in engine.edit(placed, INSERTED, engine.Insert(start, film.runtime), mode)}
        boxes = [replace(each, start=after[each.key].start, length=after[each.key].length) for each in before]
        entering = track.candidate_box(film, INSERTED, after[INSERTED].start)
        if save:
            # The box first, so a lost race writes nothing; `laying` owns the rule and the create.
            laid = laying.lay_film(film.pk, entering.start)
            if laid is None:
                return None
            stored(before, boxes)
            entering = replace(entering, key=laid.pk)
        return [*boxes, entering]


# A break of more than a day is a typo, not an evening.
MOST_BREAK = 1440


def valid_break(typed):
    """Whole minutes of break, at least 0, or None (#145)."""
    typed = str(typed).strip()
    return int(typed) if typed.isascii() and typed.isdigit() and int(typed) <= MOST_BREAK else None


def arrange(utility, minutes, save):
    """The track's boxes after an arrange utility over the timetable as stored now, stored when `save`; None with no anchor or no boxes (#145).

    The ripple mode plays no part. Only starts move, so `stored` writes starts alone.
    """
    with transaction.atomic():
        before = track.stored_boxes()
        if not before or not setting.read().anchor:
            return None
        placed = [engine.Placed(each.key, each.start, each.length, each.film is not None, each.flexible) for each in before]
        after = {each.key: each for each in engine.arrange(placed, utility, minutes)}
        boxes = [replace(each, start=after[each.key].start) for each in before]
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
