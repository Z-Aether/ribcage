"""The floor set over the roster as stored: the loader for the pure `readouts.floor`, for the Roster and Compare (#33, #146)."""

from ribcage.ballot.board import candidates
from ribcage.ballot.models import BallotRecord
from ribcage.identity.models import Voter
from ribcage.readouts import floor
from ribcage.timetable import setting


def roster():
    """The voter ids in name order and their names by id, in one query."""
    voters = list(Voter.objects.order_by("display_name_key", "pk").values_list("pk", "display_name"))
    return [pk for pk, _ in voters], dict(voters)


def load():
    """Everything the floor set reads, in four queries whatever the roster: (voter ids in name order, names by id, runtimes, records, budget)."""
    ids, names = roster()
    runtimes = dict(candidates().values_list("pk", "runtime"))
    records = list(BallotRecord.objects.filter(suggestion__in=runtimes).values_list("voter_id", "suggestion_id", "score", "vetoed", "seen_it"))
    return ids, names, runtimes, records, setting.read().budget


def of_the_ballot(ids, runtimes, on_the_ballot, records, budget, set_aside=()):
    """The floor set over loaded voters, films and records, reading the ballot's films alone: a dropped film, on the timetable or not, counts for nobody (#26 §5, #164).

    `set_aside` are the voters Compare's knob sets aside; the Roster passes none, so its floor set is the stored state (#146, #167).
    """
    return floor.floor_set(ids, {pk: runtimes[pk] for pk in on_the_ballot}, records, budget, set_aside)


def of_the_roster():
    """The floor set over the roster and each voter's reason by id, in four queries (#33)."""
    ids, names, runtimes, records, budget = load()
    found = of_the_ballot(ids, runtimes, runtimes, records, budget)
    return line_of(found, names), dict(found.out)


def line_of(found, names):
    """The floor set line's data for `components/floor_line.html`: it is highlighted when anyone is out for a reason other than the admin's own knob (#146, #147, #167)."""
    return {
        "size": found.size,
        "of": found.of,
        "out": [(names[pk], reason) for pk, reason in found.out],
        "highlight": any(reason != floor.SET_ASIDE for _, reason in found.out),
    }


def change_on_removing(voter):
    """The floor set before and after `voter` is removed, for the removal confirm (#28)."""
    ids, _, runtimes, records, budget = load()
    before = of_the_ballot(ids, runtimes, runtimes, records, budget)
    after = of_the_ballot(floor.without(ids, voter.pk), runtimes, runtimes, records, budget)
    return before, after
