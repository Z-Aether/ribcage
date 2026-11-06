"""The floor set: the voters the floor is computed over, and why each other voter is out (#15, #33, #146)."""

from dataclasses import dataclass

from ribcage.readouts.placement import is_placed

NO_BALLOT = "no ballot"
NOTHING_REPRESENTABLE = "nothing representable"
SET_ASIDE = "set aside by knob"


@dataclass(frozen=True)
class FloorSet:
    """The voters in, and each voter out with the reason, in the order the voters came."""

    members: tuple
    out: tuple  # (voter, reason) pairs

    @property
    def size(self):
        return len(self.members)

    @property
    def of(self):
        return len(self.members) + len(self.out)

    @property
    def counted(self):
        """The voters the tiebreaker `leximin` ranks: the floor set, then those out for *nothing representable*; never *no ballot* or *set aside by knob* (#176)."""
        return self.members + tuple(voter for voter, reason in self.out if reason == NOTHING_REPRESENTABLE)


def floor_set(voters, runtimes, records, budget, set_aside=(), fixed_out=()):
    """The floor set over `voters` (any keys, in the order wanted), from the candidates' `runtimes` by film, the ballot `records` and the `budget`.

    `records` are (voter, film, score, vetoed, seen_it); a record on a film not in `runtimes` is a dropped film's and counts for nobody (#26 §5).
    A voter is in with a positive score on a candidate they have neither seen nor vetoed and whose runtime fits the budget alone;
    with no budget every film fits (#26 §6).
    A voter in `set_aside` is out with `SET_ASIDE` whatever else would keep them out or in (#17, #33, #167).
    A film in `fixed_out` cannot represent anyone, so a voter whose only positive film it is reads *nothing representable*; films fixed in are not weighed against it (#33, #168).
    """
    placed, representable = set(), set()
    fixed_out = set(fixed_out)
    for voter, film, score, vetoed, seen_it in records:
        if film not in runtimes:
            continue
        if is_placed((score, vetoed)):
            placed.add(voter)
        if score is not None and score > 0 and not vetoed and not seen_it and film not in fixed_out and (budget is None or runtimes[film] <= budget):
            representable.add(voter)
    set_aside = set(set_aside)
    members = tuple(each for each in voters if each in representable and each not in set_aside)
    out = tuple((each, SET_ASIDE if each in set_aside else NO_BALLOT if each not in placed else NOTHING_REPRESENTABLE) for each in voters if each not in members)
    return FloorSet(members, out)


def without(voters, removed):
    """The voters left when `removed` goes."""
    return [each for each in voters if each != removed]
