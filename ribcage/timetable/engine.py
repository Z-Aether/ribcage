"""The timetable's arithmetic over plain boxes: length, end, overlaps, screen time, elapsed time and the budget marker (#12, #22, #136).

No ORM and no clock here. A box is its start in elapsed minutes from the anchor (negative before it), its length, and whether
it is a film's; the edge that loads the database turns each stored box into one. Screen time and elapsed time are two numbers
and stay separately named: only screen time is compared with the budget (#12).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Placed:
    """A box as the engine reads it: `key` is whatever the caller wants back, `length` a film's runtime or a labelled box's own."""

    key: object
    start: int
    length: int
    is_film: bool

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
