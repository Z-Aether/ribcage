"""The track: the evening drawn as plain data, for `console/track.html` and the box component to render (#22, #136).

`build` is plain: loaded boxes, an anchor and a budget in; geometry, labels and readouts out, with no query. `load` is the one
edge that reads the database. The track is one template over a `Track`, so a later preview can answer with the same one (#139).
Every clock label is in the deployment's TIME_ZONE, read from the anchor plus elapsed minutes as real instants, so a night
crossing a clock change shows an hour twice or skips one and nothing else notices (#36).
"""

from dataclasses import dataclass
from datetime import UTC, timedelta

from django.utils import timezone

from ribcage.ballot import board
from ribcage.suggestions.models import Approval
from ribcage.timetable import engine
from ribcage.timetable.engine import Placed
from ribcage.timetable.models import Box

# The track's scale is the evening plus this share of it on each side, and never less than the floor, in minutes.
PADDING_SHARE = 0.03
PADDING_FLOOR = 10
# More hour labels than this and the axis labels every second, third... hour instead.
MOST_LABELS = 14
LABEL_EVERY = (1, 2, 3, 6, 12, 24)
# A marker past this far along labels itself on its left, so the label stays on the track.
LABEL_LEFT_FROM = 70
# An hour label this far along the track, in percent, has no room left of the edge, so the tick is left out (#136).
LABEL_ROOM_UNTIL = 92


def duration(minutes):
    """Minutes as the readouts write them: 8h25m, 9h, 35m."""
    hours, minutes = divmod(abs(minutes), 60)
    if not hours:
        return f"{minutes}m"
    return f"{hours}h{minutes:02d}m" if minutes else f"{hours}h"


def percent(value):
    return f"{value:.3f}%"


@dataclass(frozen=True)
class Loaded:
    """One stored box with what the track shows of it, read at the edge. A film box has a `film`; a labelled one a `label`."""

    key: object
    start: int
    length: int
    film: object = None
    label: str = ""
    vetoed_by: str = ""
    vetoers: str = ""
    dropped: bool = False


@dataclass(frozen=True)
class BoxView:
    """What the box component draws, with no geometry: M8's evening lays the same data out in its own way (#136)."""

    key: object
    film: object
    title: str
    starts: str
    ends: str
    length: str
    vetoed_by: str = ""
    vetoers: str = ""
    dropped: bool = False
    overlapping: bool = False
    # The panel's line: day and clock for the start and the end, like Sat 18:00 → 19:49 (#137).
    span: str = ""
    # The length in whole minutes, for a labelled box's length field (#138).
    minutes: int = 0
    # The start in elapsed minutes, which a drag snaps against the neighbours' (#139).
    start: int = 0

    @property
    def labelled(self):
        return self.film is None


@dataclass(frozen=True)
class Placement:
    box: BoxView
    left: str
    width: str
    lane: int


@dataclass(frozen=True)
class Tick:
    left: str
    label: str
    day: str = ""


@dataclass(frozen=True)
class Band:
    left: str
    width: str


@dataclass(frozen=True)
class Marker:
    left: str
    label: str
    late: bool


@dataclass(frozen=True)
class Tools:
    """The tool row's words (#22). `spare` reads *35m to spare* or *20m over*; `budget` and `spare` are None with no budget."""

    screen: str
    budget: str | None
    spare: str | None
    is_over: bool
    filled: int
    evening: str
    elapsed: str
    overlaps: int


@dataclass(frozen=True)
class Track:
    tools: Tools
    placements: tuple[Placement, ...]
    ticks: tuple[Tick, ...]
    bands: tuple[Band, ...]
    marker: Marker | None
    lanes: int
    # The scale in minutes from the anchor, which a drag reads its pointer against and sends back to keep (#139).
    scale: "Scale"

    def box(self, key):
        """The box with this key, or None: a selection naming a box gone since is no selection (#137)."""
        return next((each.box for each in self.placements if each.box.key == key), None)


@dataclass(frozen=True)
class Scale:
    start: int
    length: int

    def at(self, minute):
        return (minute - self.start) / self.length * 100

    def size(self, minutes):
        return minutes / self.length * 100


class Clock:
    """Elapsed minutes from the anchor as wall-clock time in TIME_ZONE (#36)."""

    def __init__(self, anchor):
        # Added to in UTC, since a zoned datetime adds wall-clock time and would skip or repeat nothing at a clock change.
        self.anchor = anchor.astimezone(UTC)

    def at(self, minute):
        return timezone.localtime(self.anchor + timedelta(minutes=minute))

    def hm(self, minute):
        return self.at(minute).strftime("%H:%M")

    def day_hm(self, minute):
        return self.at(minute).strftime("%a %H:%M")

    def span(self, start, end):
        """`Sat 18:00 → 19:49`, the end's day only where it is another day than the start's: `Sat 23:41 → Sun 01:16`."""
        first, last = self.at(start), self.at(end)
        return f"{self.day_hm(start)} → {self.day_hm(end) if last.date() != first.date() else self.hm(end)}"


def build(boxes, anchor, budget, scale=None):
    """The track for the loaded boxes against the anchor (an aware datetime) and the budget in minutes; None for no boxes.

    A `scale` is kept as given, which is how a drag holds the track still while the evening changes under it (#139).
    """
    if not boxes:
        return None
    placed = [Placed(box.key, box.start, box.length, box.film is not None) for box in boxes]
    reading = engine.read(placed, budget)
    span = reading.last_end - reading.first_start
    padding = max(PADDING_FLOOR, round(span * PADDING_SHARE))
    scale = scale or Scale(reading.first_start - padding, span + 2 * padding)
    clock = Clock(anchor)
    crowded = {key for overlap in reading.overlaps for key in (overlap.first, overlap.second)}
    lane_of = in_lanes(placed)
    placements = tuple(
        Placement(view_of(box, clock, box.key in crowded), percent(scale.at(box.start)), percent(scale.size(box.length)), lane_of[box.key])
        for box in boxes
    )
    marker = None
    if reading.marker is not None:
        at = scale.at(reading.marker)
        marker = Marker(percent(at), f"budget {duration(budget)}", at > LABEL_LEFT_FROM)
    return Track(
        tools=tools_of(reading, budget, clock),
        placements=placements,
        ticks=ticks_of(scale, clock),
        bands=tuple(Band(percent(scale.at(each.start)), percent(scale.size(each.end - each.start))) for each in reading.overlaps),
        marker=marker,
        lanes=max(lane_of.values()) + 1,
        scale=scale,
    )


def view_of(box, clock, overlapping):
    return BoxView(
        key=box.key,
        film=box.film,
        title=box.film.title if box.film else box.label,
        starts=clock.hm(box.start),
        ends=clock.hm(box.start + box.length),
        length=duration(box.length),
        vetoed_by=box.vetoed_by,
        vetoers=box.vetoers,
        dropped=box.dropped,
        overlapping=overlapping,
        span=clock.span(box.start, box.start + box.length),
        minutes=box.length,
        start=box.start,
    )


def in_lanes(placed):
    """Each box's row on the track: the first row free by its start, so overlapping boxes sit one above the other."""
    ends, lanes = [], {}
    for box in engine.in_start_order(placed):
        for lane, end in enumerate(ends):
            if end <= box.start:
                ends[lane] = box.end
                break
        else:
            lane = len(ends)
            ends.append(box.end)
        lanes[box.key] = lane
    return lanes


def ticks_of(scale, clock):
    """An hour label at each full local hour on the scale, the day's name at each midnight."""
    every = next((step for step in LABEL_EVERY if scale.length / 60 / step <= MOST_LABELS), LABEL_EVERY[-1])
    end = scale.start + scale.length
    minute = scale.start
    ticks = []
    while minute <= end:
        local = clock.at(minute)
        if local.minute == 0 and local.hour % every == 0:
            if scale.at(minute) <= LABEL_ROOM_UNTIL:
                ticks.append(Tick(percent(scale.at(minute)), local.strftime("%H:%M"), local.strftime("%a") if local.hour == 0 else ""))
            minute += 60 * every - 1
        minute += 1
    return tuple(ticks)


def tools_of(reading, budget, clock):
    evening = f"{clock.day_hm(reading.first_start)} → {clock.day_hm(reading.last_end)}"
    elapsed = duration(reading.elapsed)
    screen = duration(reading.screen_time)
    if budget is None:
        return Tools(screen, None, None, False, 0, evening, elapsed, len(reading.overlaps))
    over = reading.over
    spare = f"{duration(over)} over" if over > 0 else f"{duration(-over)} to spare"
    filled = 100 if over > 0 else round(reading.screen_time / budget * 100)
    return Tools(screen, duration(budget), spare, over > 0, filled, evening, elapsed, len(reading.overlaps))


def load(anchor, budget):
    """Read the timetable's boxes and build its track: two queries however many boxes there are (one with no film box)."""
    return build(stored_boxes(), anchor, budget)


def stored_boxes():
    """The timetable's boxes as the track shows them, in start order."""
    stored = list(Box.objects.select_related("suggestion").order_by("start", "pk"))
    marks = board.veto_marks(board.vetoes_on([box.suggestion_id for box in stored if box.suggestion_id]), None)
    boxes = []
    for box in stored:
        if box.suggestion is None:
            boxes.append(Loaded(box.pk, box.start, box.length, label=box.label))
            continue
        initials, names = marks.get(box.suggestion_id, ("", ""))
        boxes.append(
            Loaded(
                box.pk,
                box.start,
                box.suggestion.runtime,
                film=box.suggestion.film,
                vetoed_by=initials,
                vetoers=names,
                # The mark is the admin's alone; voters never see approval (#26 §5).
                dropped=box.suggestion.approval == Approval.DROPPED,
            )
        )
    return boxes
