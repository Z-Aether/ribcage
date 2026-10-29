"""The header's two values, the anchor and the budget, and the writes that set them (#12, #36, #135)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from django.utils import timezone

from ribcage.timetable.models import Timetable

# Hours beyond this are a typo, and keep the minutes within what the database holds.
MOST_HOURS = 99
NO_ANCHOR = "Type the start date and time, like 2026-11-07 18:00. The start can be changed, but not emptied."
NO_BUDGET = "Type hours and minutes, like 9 and 30, or leave both blank for no budget."


@dataclass(frozen=True)
class Refused:
    """A header field's refused post: what was typed, kept in the box, and why (#97, #135)."""

    field: str
    typed: tuple
    says: str


def read():
    """The timetable, or an unsaved empty one where nothing has set it."""
    return Timetable.objects.filter(pk=1).first() or Timetable(pk=1)


def local_anchor(anchor):
    """The anchor as the deployment's own clock reads it, or None."""
    return timezone.localtime(anchor) if anchor else None


def set_anchor(typed):
    """Set the anchor from a local date and time in TIME_ZONE, or return a Refused. An ambiguous time is Django's to resolve (#36)."""
    try:
        naive = datetime.fromisoformat(typed.strip())
    except ValueError:
        return Refused("anchor", (typed,), NO_ANCHOR)
    if naive.tzinfo is not None or not typed.strip():
        return Refused("anchor", (typed,), NO_ANCHOR)
    try:
        anchor = timezone.make_aware(naive)
        anchor.astimezone(UTC)  # a local time at the calendar's first edge has no UTC instant
    except OverflowError:
        return Refused("anchor", (typed,), NO_ANCHOR)
    Timetable.objects.update_or_create(pk=1, defaults={"anchor": anchor})
    return None


def set_budget(hours, minutes):
    """Set the budget from hours and minutes, or clear it where both are blank; else return a Refused (#26 §6)."""
    typed = (hours, minutes)
    if not hours.strip() and not minutes.strip():
        Timetable.objects.update_or_create(pk=1, defaults={"budget": None})
        return None
    try:
        whole_hours, whole_minutes = int(hours.strip() or 0), int(minutes.strip() or 0)
    except ValueError:
        return Refused("budget", typed, NO_BUDGET)
    total = whole_hours * 60 + whole_minutes
    if not (0 <= whole_hours <= MOST_HOURS and 0 <= whole_minutes < 60 and total > 0):
        return Refused("budget", typed, NO_BUDGET)
    Timetable.objects.update_or_create(pk=1, defaults={"budget": total})
    return None
