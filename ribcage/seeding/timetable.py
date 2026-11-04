"""The seeded timetable: in PICK and RUN, the next Saturday at 18:00, a 9 hour budget and a hand-built evening within it, and one kept proposal; earlier phases leave all empty (#135, #136, #169)."""

from datetime import datetime, time, timedelta

from django.utils import timezone

from ribcage.ballot import floor
from ribcage.readouts.basis import Basis, label
from ribcage.shortlist import keeping
from ribcage.suggestions.models import Suggestion
from ribcage.timetable.models import Box, Timetable

SEEDED_START = time(18, 0)
SEEDED_BUDGET = 9 * 60
SATURDAY = 5
# Far enough ahead to set the evening up in (#135).
AT_LEAST_DAYS = 2

WEREWOLF_BY_NIGHT, KILLER_KLOWNS, WHEN_EVIL_LURKS, EXIT_8, CUBE, TERRIFIER = 894205, 16296, 744857, 1408208, 431, 420634
DINNER = "Dinner"
DINNER_LENGTH = 45
# Each box is (a film's TMDB id, or the label of a labelled box) and the gap before it, in minutes: 10 to 20 apart, no overlap.
# When Evil Lurks, which Sam vetoes, sits mid-evening for #149's strip, and Terrifier, which Zoë and Anne-Marie veto, comes last.
# Six films run 510 of the 540 minutes; the other eight approved films are left off for the candidate list (#137).
SEEDED_EVENING = (
    (WEREWOLF_BY_NIGHT, 0),
    (KILLER_KLOWNS, 10),
    (DINNER, 15),
    (WHEN_EVIL_LURKS, 10),
    (EXIT_8, 20),
    (CUBE, 15),
    (TERRIFIER, 10),
)


def next_saturday(today):
    ahead = (SATURDAY - today.weekday()) % 7
    return today + timedelta(days=ahead if ahead >= AT_LEAST_DAYS else ahead + 7)


def seed_the_timetable():
    day = next_saturday(timezone.localdate())
    anchor = timezone.make_aware(datetime.combine(day, SEEDED_START))
    Timetable.objects.create(pk=1, anchor=anchor, budget=SEEDED_BUDGET)
    films = {suggestion.tmdb_id: suggestion for suggestion in Suggestion.objects.exclude(tmdb_id=None)}
    at = 0
    for what, gap in SEEDED_EVENING:
        start = at + gap
        if what == DINNER:
            Box.objects.create(label=DINNER, length=DINNER_LENGTH, start=start)
            at = start + DINNER_LENGTH
        else:
            Box.objects.create(suggestion=films[what], start=start)
            at = start + films[what].runtime


# The kept proposal, found under a knob the seed leaves off, so its provenance reads rescored under the current basis (#169).
KEPT_FILMS = (WEREWOLF_BY_NIGHT, EXIT_8, CUBE, TERRIFIER)
KEPT_UNDER = "Sam"


def seed_the_shortlist():
    ids, names = floor.roster()
    sam = next(pk for pk in ids if names[pk] == KEPT_UNDER)
    films = {suggestion.tmdb_id: suggestion for suggestion in Suggestion.objects.exclude(tmdb_id=None)}
    keeping.keep([films[each].pk for each in KEPT_FILMS], label(Basis(disregarded=frozenset({sam})), ids, names))
