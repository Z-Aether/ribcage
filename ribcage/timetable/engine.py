"""The timetable's arithmetic over plain boxes: length, end, overlaps, screen time, elapsed time and the budget marker (#12, #22, #136).

No ORM and no clock here. A box is its start in elapsed minutes from the anchor (negative before it), its length, and whether
it is a film's; the edge that loads the database turns each stored box into one. Screen time and elapsed time are two numbers
and stay separately named: only screen time is compared with the budget (#12).
"""

from dataclasses import dataclass, replace
from math import ceil, floor


@dataclass(frozen=True)
class Placed:
    """A box as the engine reads it: `key` is whatever the caller wants back, `length` a film's runtime or a labelled box's own."""

    key: object
    start: int
    length: int
    is_film: bool
    # A flexible box keeps its full length under Push · keep gaps; #141's squeeze is what reads this (#22, #140).
    flexible: bool = False

    @property
    def end(self):
        return self.start + self.length


@dataclass(frozen=True)
class Overlap:
    """Two boxes sharing the minutes from `start` to `end` (#12)."""

    first: object
    second: object
    start: int
    end: int


@dataclass(frozen=True)
class Reading:
    """Everything the tool row and the track read off the boxes."""

    screen_time: int
    elapsed: int
    first_start: int | None
    last_end: int | None
    overlaps: tuple[Overlap, ...]
    # Minutes from the anchor where cumulative screen time runs out; None within the budget and with none.
    marker: int | None
    # Screen time minus the budget: negative is minutes to spare; None with no budget.
    over: int | None


def in_start_order(boxes):
    return sorted(boxes, key=lambda box: (box.start, box.end))


def screen_time(boxes):
    """The films' runtimes summed; a labelled box is no screen time."""
    return sum(box.length for box in boxes if box.is_film)


def elapsed_time(boxes):
    """From the first box's start to the last box's end, gaps and labelled boxes included."""
    if not boxes:
        return 0
    return max(box.end for box in boxes) - min(box.start for box in boxes)


def overlaps(boxes):
    """Every pair of boxes sharing minutes, a film and a labelled box included. Boxes that only touch share none."""
    ordered = in_start_order(boxes)
    found = []
    for index, first in enumerate(ordered):
        for second in ordered[index + 1 :]:
            # Sorted by start, so once one starts at or after this end, the rest do too.
            if second.start >= first.end:
                break
            found.append(Overlap(first.key, second.key, second.start, min(first.end, second.end)))
    return tuple(found)


def budget_marker(boxes, budget):
    """The minute cumulative screen time runs out, counting films in start order, or None with no budget or within it (#22)."""
    if budget is None or screen_time(boxes) <= budget:
        return None
    used = 0
    for box in in_start_order([each for each in boxes if each.is_film]):
        if used + box.length >= budget:
            return box.start + (budget - used)
        used += box.length
    return None


def read(boxes, budget):
    boxes = list(boxes)
    screen = screen_time(boxes)
    return Reading(
        screen_time=screen,
        elapsed=elapsed_time(boxes),
        first_start=min((box.start for box in boxes), default=None),
        last_end=max((box.end for box in boxes), default=None),
        overlaps=overlaps(boxes),
        marker=budget_marker(boxes, budget),
        over=None if budget is None else screen - budget,
    )


# The ripple modes (#13): a name each, and in `RIPPLE_MODES` the function that acts on the edit.
NONE = "none"
KEEP_GAPS = "keep-gaps"
KEEP_END_TIME = "keep-end-time"


@dataclass(frozen=True)
class Move:
    """A box's new start, in elapsed minutes from the anchor; negative is before it (#139)."""

    start: int


@dataclass(frozen=True)
class Resize:
    """A box's new length in minutes, a labelled box's own or a film's corrected runtime; its start stays (#140, #142). The drag handle joins as #143 lands."""

    length: int


# An inserted box (#144) joins as its own class, and `apply` learns it. Every change goes through `edit`, so a preview and a save
# are the same call (#22).


def apply(boxes, key, change):
    """The edited box alone, changed as the change says, before any ripple mode acts."""
    if isinstance(change, Move):
        return [replace(box, start=change.start) if box.key == key else box for box in boxes]
    if isinstance(change, Resize):
        return [replace(box, length=change.length) if box.key == key else box for box in boxes]
    raise TypeError(f"not a change: {change!r}")


def leave_alone(before, after, key):
    """None: the edited box changed and nothing else does; any overlap it makes is left for `overlaps` to flag (#12, #139)."""
    return after


def pushed_side(before, after, key):
    """The boxes an edit pushes and by how much, as (side, delta, later), or None where nothing is touched (#13, #140).

    A later end pushes every other box starting at or after the edited box's old start, by the end's delta. An earlier start
    pushes every box starting before the old start, by the start's delta. A move short of contact pushes nothing, and so does a
    shorter box: dragging back never undoes a push.
    """
    old = next((box for box in before if box.key == key), None)
    new = next((box for box in after if box.key == key), None)
    if old is None or new is None:
        return None
    if new.end > old.end:
        side = [box for box in after if box.key != key and box.start >= old.start]
        touched = bool(side) and new.end > min(box.start for box in side)
        return (side, new.end - old.end, True) if touched else None
    if new.start < old.start:
        side = [box for box in after if box.key != key and box.start < old.start]
        touched = bool(side) and new.start < max(box.end for box in side)
        return (side, new.start - old.start, False) if touched else None
    return None


def keep_gaps(before, after, key):
    """Push · keep gaps: once the edited box touches into its neighbour, every box on that side moves by the edit's own delta (#13, #22, #140)."""
    pushed = pushed_side(before, after, key)
    if pushed is None:
        return after
    side, delta, _ = pushed
    moved = {box.key for box in side}
    return [replace(box, start=box.start + delta) if box.key in moved else box for box in after]


# A flexible box never shrinks below one step of the 5-minute grid (#22, #141).
FLOOR = 5
GRID = 5


def on_grid(minute):
    """The nearest 5-minute mark, halves rounding up."""
    return floor(minute / GRID + 0.5) * GRID


def grid_up(minute):
    """The first 5-minute mark at or after the minute."""
    return ceil(minute / GRID) * GRID


def grid_down(minute):
    """The last 5-minute mark at or before the minute."""
    return floor(minute / GRID) * GRID


def latest_ends(items, edge):
    """Mirrored: for each box, the latest reflected end, so the earliest real start, that still lets the boxes before it in real time start on a mark from the held edge."""
    latest, start = [0] * len(items), -edge
    for index in reversed(range(len(items))):
        if index != len(items) - 1:
            start = grid_up(start)
        latest[index] = -start
        start += FLOOR if items[index].flexible else items[index].length
    return latest


def squeezed(items, old_end, new_end, mirrored=False):
    """The side's boxes after the squeeze, later than the edited box's end: gaps and flexible boxes give up the edit's delta between them (#22, #141).

    The outer edge, the last end, holds. Each gap and each flexible box above `FLOOR` gives up the same fraction of what it can
    give, never below zero or `FLOOR`. Each start is rounded to the grid one by one, and each box's share is recomputed from where the box before really
    ended, so the residue never accumulates and the edge lands within 2.5 minutes; a start that would fall behind the box before it (an odd-length film
    with its gap squeezed out) rounds up to the next mark instead. With no slack left, boxes pack flat against the edited box's
    end, flush and off the grid, as keep gaps pushes by the delta. `mirrored` is the earlier edit seen from the other end, where
    the real start is the reflected end, so that is what is rounded, and the held edge, the first real start, goes back to exactly where it was
    while the boxes after it can still start on marks from it.
    """
    items = in_start_order(items)
    edge = max(box.end for box in items)
    gaps, reach = [], old_end
    for box in items:
        gaps.append(max(0, box.start - reach))
        reach = max(reach, box.end)
    give = [max(0, box.length - FLOOR) if box.flexible else 0 for box in items]
    if sum(box.length for box in items) + sum(gaps) - (edge - new_end) <= 0:
        return items
    squeezed_items, cursor = [], new_end
    latest = latest_ends(items, edge) if mirrored else []
    for index, box in enumerate(items):
        gap, spare = gaps[index], give[index]
        # What is still owed over what is still giveable, from where the last box really ended: rounding residue is taken up by the boxes after.
        owed = sum(each.length for each in items[index:]) + sum(gaps[index:]) - (edge - cursor)
        room = sum(gaps[index:]) + sum(give[index:])
        share = 1 if room == 0 else max(0, min(1, owed / room))
        if share >= 1:
            start, length = cursor, box.length - spare
        elif mirrored:
            start = max(cursor, on_grid(cursor + gap * (1 - share)) if spare else cursor + gap * (1 - share))
            if spare:
                if index == len(items) - 1:
                    # The last box mirrored is the first one really, and the held edge is its start: back to exactly where it was.
                    end = min(edge, start + box.length)
                else:
                    end = min(on_grid(start + box.length - spare * share), grid_down(start + box.length), latest[index])
                length = max(FLOOR, end - start)
            else:
                end = max(min(on_grid(start + box.length), latest[index]), grid_up(cursor + box.length))
                start, length = end - box.length, box.length
        else:
            start = max(grid_up(cursor), on_grid(cursor + gap * (1 - share)))
            length = box.length
            if spare:
                length = min(box.length, on_grid(start + box.length - spare * share) - start)
        squeezed_items.append(replace(box, start=start, length=length))
        cursor = start + length
    return squeezed_items


def reflected(box):
    """The box seen from the other end of the evening, so an earlier push is a later one."""
    return replace(box, start=-box.end)


def keep_end_time(before, after, key):
    """Push · keep end time: the edit's delta is taken out of the gaps and flexible boxes on the pushed side, so its outer edge holds (#13, #22, #141).

    Contact, the side and the delta are keep gaps'. An earlier edit holds the first box's start, the same squeeze mirrored.
    """
    pushed = pushed_side(before, after, key)
    if pushed is None:
        return after
    side, _, later = pushed
    old = next(box for box in before if box.key == key)
    new = next(box for box in after if box.key == key)
    if later:
        result = {box.key: box for box in squeezed(side, old.end, new.end)}
    else:
        result = {box.key: reflected(box) for box in squeezed([reflected(each) for each in side], -old.start, -new.start, mirrored=True)}
    return [result.get(box.key, box) for box in after]


RIPPLE_MODES = {NONE: leave_alone, KEEP_GAPS: keep_gaps, KEEP_END_TIME: keep_end_time}
MODES = tuple(RIPPLE_MODES)


def edit(boxes, key, change, mode):
    """The boxes after one change to the box `key` under a ripple mode; nothing is mutated, so a preview and a save can share it."""
    if mode not in RIPPLE_MODES:
        raise ValueError(f"not a mode: {mode!r}")
    boxes = list(boxes)
    return RIPPLE_MODES[mode](boxes, apply(boxes, key, change), key)
