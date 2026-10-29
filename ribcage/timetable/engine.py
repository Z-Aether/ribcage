"""The timetable's arithmetic over plain boxes: length, end, overlaps, screen time, elapsed time and the budget marker (#12, #22, #136).

No ORM and no clock here. A box is its start in elapsed minutes from the anchor (negative before it), its length, and whether
it is a film's; the edge that loads the database turns each stored box into one. Screen time and elapsed time are two numbers
and stay separately named: only screen time is compared with the budget (#12).
"""

from dataclasses import dataclass, replace


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


# The ripple modes (#13): a name each, and in `RIPPLE_MODES` the function that acts on the edit. #141 adds a name and its function.
NONE = "none"
KEEP_GAPS = "keep-gaps"


@dataclass(frozen=True)
class Move:
    """A box's new start, in elapsed minutes from the anchor; negative is before it (#139)."""

    start: int


@dataclass(frozen=True)
class Resize:
    """A labelled box's new length in minutes; its start stays (#140). A film's runtime and the drag handle join as #142 and #143 land."""

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


def keep_gaps(before, after, key):
    """Push · keep gaps: once the edited box touches into its neighbour, every box on that side moves by the edit's own delta (#13, #22, #140).

    A later end (a move later, a longer box) pushes every other box starting at or after the edited box's old start, by the
    end's delta. An earlier start pushes every box starting before the old start, by the start's delta, which may carry them
    before the anchor. A move short of contact pushes nothing, and so does a shorter box: dragging back never undoes a push.
    """
    old = next((box for box in before if box.key == key), None)
    new = next((box for box in after if box.key == key), None)
    if old is None or new is None:
        return after
    if new.end > old.end:
        side = [box for box in after if box.key != key and box.start >= old.start]
        delta = new.end - old.end
        touched = bool(side) and new.end > min(box.start for box in side)
    elif new.start < old.start:
        side = [box for box in after if box.key != key and box.start < old.start]
        delta = new.start - old.start
        touched = bool(side) and new.start < max(box.end for box in side)
    else:
        return after
    if not touched:
        return after
    pushed = {box.key for box in side}
    return [replace(box, start=box.start + delta) if box.key in pushed else box for box in after]


RIPPLE_MODES = {NONE: leave_alone, KEEP_GAPS: keep_gaps}
MODES = tuple(RIPPLE_MODES)


def edit(boxes, key, change, mode):
    """The boxes after one change to the box `key` under a ripple mode; nothing is mutated, so a preview and a save can share it."""
    if mode not in RIPPLE_MODES:
        raise ValueError(f"not a mode: {mode!r}")
    boxes = list(boxes)
    return RIPPLE_MODES[mode](boxes, apply(boxes, key, change), key)
