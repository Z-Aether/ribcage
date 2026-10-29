"""The floor set over the roster as stored: the loader for the pure `readouts.floor`, for the Roster and Compare (#33, #146)."""

from ribcage.ballot.board import candidates
from ribcage.ballot.models import BallotRecord
from ribcage.identity.models import Voter
from ribcage.readouts import floor
from ribcage.timetable import setting


def load():
    """Everything the floor set reads, in four queries whatever the roster: (voter ids in name order, names by id, runtimes, records, budget)."""
    voters = list(Voter.objects.order_by("display_name_key", "pk").values_list("pk", "display_name"))
    runtimes = dict(candidates().values_list("pk", "runtime"))
    records = list(BallotRecord.objects.filter(suggestion__in=runtimes).values_list("voter_id", "suggestion_id", "score", "vetoed", "seen_it"))
    return [pk for pk, _ in voters], dict(voters), runtimes, records, setting.read().budget


def of_the_roster():
    """The floor set over the roster and each voter's reason by id, in four queries (#33)."""
    ids, names, runtimes, records, budget = load()
    found = floor.floor_set(ids, runtimes, records, budget)
    return line_of(found, names), dict(found.out)


def line_of(found, names):
    """The floor set line's data for `components/floor_line.html` (#146, #147)."""
    return {"size": found.size, "of": found.of, "out": [(names[pk], reason) for pk, reason in found.out]}


def change_on_removing(voter):
    """The floor set before and after `voter` is removed, for the removal confirm (#28)."""
    ids, _, runtimes, records, budget = load()
    before = floor.floor_set(ids, runtimes, records, budget)
    after = floor.floor_set(floor.without(ids, voter.pk), runtimes, records, budget)
    return before, after
