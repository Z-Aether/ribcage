"""The set readouts of the timetable's slate as stored: the loader for the pure `readouts.plan`, for Compare (#147)."""

from ribcage.ballot import floor as ballot_floor
from ribcage.ballot.models import BallotRecord
from ribcage.readouts import floor, plan
from ribcage.readouts.slate import SlateEntry, film_points, slate_order
from ribcage.timetable.models import Box


def load():
    """The plan's readouts as the page shows them, in six queries however long the slate is (#147).

    #148's film points and slate sums join the dict beside these.
    """
    ids, names, runtimes, records, budget = ballot_floor.load()
    found = floor.floor_set(ids, runtimes, records, budget)
    boxes = list(Box.objects.order_by("start", "pk").values_list("suggestion_id", "suggestion__title", "suggestion__runtime"))
    on_the_plan = [each for each in boxes if each[0] is not None]
    titles = {pk: title for pk, title, _ in on_the_plan}
    held = list(BallotRecord.objects.filter(suggestion__in=titles).values_list("voter_id", "suggestion_id", "score", "vetoed", "seen_it"))
    # Slate order, not box order, so a move changes neither a tie's representative nor the Vetoed list (#36, #12).
    by_film = {}
    for _, film, score, vetoed, _ in held:
        by_film.setdefault(film, []).append((score, vetoed))
    standings = [
        SlateEntry(pk, title, sum(1 for _, vetoed in by_film.get(pk, ()) if vetoed), film_points(by_film.get(pk, ()))) for pk, title in titles.items()
    ]
    slate = [each.key for each in slate_order(standings)]
    read = plan.plan(ids, slate, {pk: runtime for pk, _, runtime in on_the_plan}, held, found, budget)
    return {
        "empty": not boxes,
        "films": read.films,
        "screen_time": plan.clock(read.screen_time),
        "budget": None if read.budget is None else plan.clock(read.budget),
        "over": read.over,
        "floor": read.floor,
        "sigma_rep": read.sigma_rep,
        "floor_line": ballot_floor.line_of(found, names),
        "rows": [
            {"name": names[each.voter], "film": titles.get(each.representative), "score": each.representation, "out": each.out, "pins": each.pins} for each in read.rows
        ],
        "vetoed": [{"film": titles[each.film], "by": [names[voter] for voter in each.vetoers]} for each in read.vetoed],
    }
