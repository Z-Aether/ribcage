"""The evening: the published timetable as a voter reads it in RUN, drawn as plain data for `components/evening.html` (#155).

`build` is plain: loaded boxes and an anchor in, geometry out, with no query; `load` is the one edge that reads the database.
It draws the same loaded boxes as the admin's track through the same `BoxView`s, but lays them out its own way, with the scale
fitted exactly from the first start to the last end, and none of the admin's readouts: no strips, vetoers, dropped mark,
overlap mark or budget (#22, #149). Each box carries its start and end as instants and the region the evening's span, which
#159 marks the boxes from and #160 swaps the region by.
"""

from dataclasses import dataclass, replace
from datetime import UTC, timedelta

from django.utils import timezone

from ribcage.timetable import setting, track
from ribcage.timetable.engine import NEXT, PLAYING, Placed, in_words, now_playing


# What the evening reads with nothing to show; the Phase tab's publish sentence names it too (#156).
EMPTY_LINE = "The running order isn't out yet."


def whats_missing(has_boxes, anchor):
    """What leaves the evening with nothing to show, from "start time" and "boxes"; the one rule `build` and the Phase tab share (#156)."""
    return [name for name, present in [("start time", anchor is not None), ("boxes", has_boxes)] if not present]


@dataclass(frozen=True)
class Slot:
    """One box placed on the fitted scale: percentages of the evening's height and width, and its instants as ISO strings."""

    box: track.BoxView
    top: str
    height: str
    left: str
    width: str
    starts_at: str
    ends_at: str
    # Where the night is at the request's instant (#159): past, playing, next or later, the words a playing or next box wears, and the elapsed share.
    state: str = "later"
    status: str = ""
    elapsed: str = "0.000%"


def status_of(moment):
    """The line a playing or next box wears: `NOW PLAYING · 42m left`, `NEXT · in 25m`; the phone's script words the same (#159)."""
    if moment.state == PLAYING:
        return f"NOW PLAYING · {in_words(moment.minutes_left)} left"
    if moment.state == NEXT:
        return f"NEXT · in {in_words(moment.minutes_until)}"
    return ""


@dataclass(frozen=True)
class Evening:
    slots: tuple[Slot, ...] = ()
    # The span the scale fits, as instants (ISO strings) and whole minutes; empty with nothing to show.
    starts_at: str = ""
    ends_at: str = ""
    minutes: int = 0

    @property
    def empty(self):
        return not self.slots

    @property
    def empty_line(self):
        return EMPTY_LINE


def instant(anchor, minute):
    return (anchor.astimezone(UTC) + timedelta(minutes=minute)).isoformat()


def plain(box):
    """The box without what only the admin sees: vetoers, the dropped mark, the veto voters and the flexible arrow (#26 section 5, #149)."""
    return replace(box, vetoed_by="", vetoers="", dropped=False, veto_voters=frozenset(), flexible=False)


def states_of(moment):
    if moment is None:
        return ()
    return moment.state, status_of(moment), track.percent(moment.elapsed * 100)


def build(boxes, anchor, now=None):
    """The evening for the loaded boxes against the anchor (an aware datetime); an empty one with no boxes or no anchor.

    `now` is the instant the states are read at; without it every box is later (#159)."""
    if whats_missing(bool(boxes), anchor):
        return Evening()
    boxes = [plain(box) for box in boxes]
    first = min(box.start for box in boxes)
    last = max(box.start + box.length for box in boxes)
    minutes = last - first
    clock = track.Clock(anchor)
    where = {}
    if now is not None:
        elapsed = (now - anchor).total_seconds() / 60
        where = now_playing([Placed(box.key, box.start, box.length, box.film is not None) for box in boxes], elapsed)
    lane_of = track.in_lanes([Placed(box.key, box.start, box.length, box.film is not None) for box in boxes])
    lanes = max(lane_of.values()) + 1
    slots = tuple(
        Slot(
            track.view_of(box, clock, False),
            track.percent((box.start - first) / minutes * 100),
            track.percent(box.length / minutes * 100),
            track.percent(lane_of[box.key] / lanes * 100),
            track.percent(100 / lanes),
            instant(anchor, box.start),
            instant(anchor, box.start + box.length),
            *states_of(where.get(box.key)),
        )
        for box in boxes
    )
    return Evening(slots, instant(anchor, first), instant(anchor, last), minutes)


def load():
    """The timetable as it stands, read now: advancing to RUN is publishing, and nothing is stored (#12, #26)."""
    return build(track.stored_boxes(), setting.read().anchor, timezone.now())
