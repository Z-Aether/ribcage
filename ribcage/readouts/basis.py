"""The basis: the knob settings in force, one plain value the solver and every readout take; knobs never touch stored votes (#11, #17, #167)."""

from dataclasses import dataclass, replace

from ribcage.readouts.slate import DISREGARDED

NO_KNOBS = "no knobs"


@dataclass(frozen=True)
class Basis:
    """The voters set aside ("without"), the voters whose vetoes are disregarded and the films fixed in and out; a film is never both (#17, #168)."""

    without: frozenset = frozenset()
    disregarded: frozenset = frozenset()
    fixed_in: frozenset = frozenset()
    fixed_out: frozenset = frozenset()

    def __bool__(self):
        return bool(self.without or self.disregarded or self.fixed_in or self.fixed_out)

    def fixing(self, film, way, on):
        """The basis with `film` fixed `way` ("fixed_in" or "fixed_out") or released; fixing it one way clears the other (#168)."""
        other = "fixed_out" if way == "fixed_in" else "fixed_in"
        kept = getattr(self, way)
        return replace(self, **{way: kept | {film} if on else kept - {film}, other: getattr(self, other) - {film} if on else getattr(self, other)})


def under(records, basis):
    """The (voter, film, score, vetoed, seen_it) records as the basis counts them, the stored ones left as they are (#167).

    A voter set aside has none, so they leave every film's points, the slate sums and the total; a disregarded veto stays a veto, which bars the film, but scores 0.
    """
    return tuple(
        (voter, film, score, DISREGARDED if vetoed and voter in basis.disregarded else vetoed, seen_it)
        for voter, film, score, vetoed, seen_it in records
        if voter not in basis.without
    )


def label(basis, ids, names, films=(), titles=None):
    """The basis line, *without Dani · Eszter's vetoes disregarded · Weapons fixed in · Coco fixed out*, or *no knobs*; voters in the order of `ids`, films in the order of `films` (#24, #167, #168)."""
    parts = []
    if gone := [names[each] for each in ids if each in basis.without]:
        parts.append("without " + ", ".join(gone))
    if kept := [names[each] for each in ids if each in basis.disregarded]:
        parts.append(", ".join(f"{each}'s" for each in kept) + " vetoes disregarded")
    for way, says in (("fixed_in", "fixed in"), ("fixed_out", "fixed out")):
        if named := [titles[each] for each in films if each in getattr(basis, way)]:
            parts.append(", ".join(named) + " " + says)
    return " · ".join(parts) or NO_KNOBS
