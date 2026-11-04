"""The basis: the knob settings in force, one plain value the solver and every readout take; knobs never touch stored votes (#11, #17, #167)."""

from dataclasses import dataclass

from ribcage.readouts.slate import DISREGARDED

NO_KNOBS = "no knobs"


@dataclass(frozen=True)
class Basis:
    """The voters set aside ("without") and the voters whose vetoes are disregarded; #168 adds the films fixed in and out."""

    without: frozenset = frozenset()
    disregarded: frozenset = frozenset()

    def __bool__(self):
        return bool(self.without or self.disregarded)


def under(records, basis):
    """The (voter, film, score, vetoed, seen_it) records as the basis counts them, the stored ones left as they are (#167).

    A voter set aside has none, so they leave every film's points, the slate sums and the total; a disregarded veto stays a veto, which bars the film, but scores 0.
    """
    return tuple(
        (voter, film, score, DISREGARDED if vetoed and voter in basis.disregarded else vetoed, seen_it)
        for voter, film, score, vetoed, seen_it in records
        if voter not in basis.without
    )


def label(basis, ids, names):
    """The basis line, *without Dani · Eszter's vetoes disregarded*, or *no knobs*; voters in the order of `ids` (#24, #167)."""
    parts = []
    if gone := [names[each] for each in ids if each in basis.without]:
        parts.append("without " + ", ".join(gone))
    if kept := [names[each] for each in ids if each in basis.disregarded]:
        parts.append(", ".join(f"{each}'s" for each in kept) + " vetoes disregarded")
    return " · ".join(parts) or NO_KNOBS
