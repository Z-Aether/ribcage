"""Presence strips and shared time, over plain data: who is in the room when, as a pure function of the vetoes on the timetable's films and their start order (#10, #11, #12, #149).

Nothing is entered and no voter is asked: a strip is derived from the vetoes alone, whatever the film's approval (#26 §5). Labelled boxes
are ignored for order but count for the evening's span. Minutes are elapsed minutes from the anchor, as `timetable.engine` reads them.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Showing:
    """A box as the rule reads it: a film's carries the voters who vetoed it, a labelled box's `is_film` is False."""

    key: object
    start: int
    end: int
    is_film: bool
    vetoers: frozenset = frozenset()


@dataclass(frozen=True)
class Hole:
    """A vetoed film inside a strip: the minutes the voter steps out for."""

    film: object
    start: int
    end: int


@dataclass(frozen=True)
class Strip:
    """When a voter is in the room. `empty` is a voter who vetoed every film: they are never there, and arrive and leave are both the evening's end."""

    voter: object
    arrive: int
    leave: int
    holes: tuple
    empty: bool = False


@dataclass(frozen=True)
class Presence:
    """The strips of the voters not present throughout, how many are, and the shared time with the pieces of the evening it is made of."""

    strips: tuple
    throughout: int
    shared: int
    shared_pieces: tuple  # (start, end) pairs, in order


def presence(voters, boxes):
    """The presence of `voters` (any keys, in the order wanted) over `boxes`, a sequence of `Showing`."""
    boxes = list(boxes)
    if not boxes:
        return Presence((), len(voters), 0, ())
    first, last = min(box.start for box in boxes), max(box.end for box in boxes)
    # Films starting together stay in the order the caller gave: the box's own order.
    films = sorted((box for box in boxes if box.is_film), key=lambda box: box.start)
    strips = []
    for voter in voters:
        vetoed = [voter in film.vetoers for film in films]
        if not any(vetoed):
            continue
        strips.append(strip_of(voter, films, vetoed, first, last))
    if not strips:
        return Presence((), len(voters), last - first, ((first, last),))
    arrive, leave = max(each.arrive for each in strips), min(each.leave for each in strips)
    pieces = pieces_without(arrive, leave, [(hole.start, hole.end) for each in strips for hole in each.holes])
    return Presence(tuple(strips), len(voters) - len(strips), sum(end - start for start, end in pieces), pieces)


def strip_of(voter, films, vetoed, first, last):
    leading = next((index for index, each in enumerate(vetoed) if not each), len(films))
    if leading == len(films):
        return Strip(voter, last, last, (), empty=True)
    trailing = max(index for index, each in enumerate(vetoed) if not each)
    arrive = max(film.end for film in films[:leading]) if leading else first
    leave = films[trailing + 1].start if trailing + 1 < len(films) else last
    holes = tuple(Hole(films[index].key, films[index].start, films[index].end) for index in range(leading, trailing + 1) if vetoed[index])
    return Strip(voter, arrive, leave, holes)


def pieces_without(start, end, holes):
    """What is left of start..end once every hole is taken out, once each however many holes share the minutes."""
    pieces, at = [], start
    for hole_start, hole_end in sorted(holes):
        if hole_end <= at:
            continue
        if hole_start >= end:
            break
        if hole_start > at:
            pieces.append((at, hole_start))
        at = max(at, hole_end)
    if at < end:
        pieces.append((at, end))
    return tuple(pieces)
