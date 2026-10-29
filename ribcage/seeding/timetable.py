"""The seeded timetable's header: in PICK and RUN, the next Saturday at 18:00 and 9 hours; earlier phases leave both empty (#135)."""

from datetime import datetime, time, timedelta

from django.utils import timezone

from ribcage.timetable.models import Timetable

SEEDED_START = time(18, 0)
SEEDED_BUDGET = 9 * 60
SATURDAY = 5
# Far enough ahead to set the evening up in (#135).
AT_LEAST_DAYS = 2


def next_saturday(today):
    ahead = (SATURDAY - today.weekday()) % 7
    return today + timedelta(days=ahead if ahead >= AT_LEAST_DAYS else ahead + 7)


def seed_the_timetable():
    day = next_saturday(timezone.localdate())
    anchor = timezone.make_aware(datetime.combine(day, SEEDED_START))
    Timetable.objects.create(pk=1, anchor=anchor, budget=SEEDED_BUDGET)
