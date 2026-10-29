"""The set readouts of the timetable's slate as stored: the loader for the pure `readouts.plan`, for Compare (#147)."""

from ribcage.ballot import floor as ballot_floor
from ribcage.ballot.board import candidates
from ribcage.ballot.models import BallotRecord
from ribcage.readouts import floor, plan
from ribcage.readouts.slate import SlateEntry, film_points, slate_order
from ribcage.timetable.models import Box


def load():
    """The plan's readouts as the page shows them, in seven queries however long the slate is (#147, #148).

    The breakdown (film points, slate sums, a voter at zero's best eligible film) is the one more query, for the candidates' titles and runtimes.
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
    on_the_ballot = {}
    for _, film, score, vetoed, _ in records:
        on_the_ballot.setdefault(film, []).append((score, vetoed))
    the_ballot = list(candidates().values_list("pk", "title", "runtime"))
    ranked = slate_order(
        [
            SlateEntry(pk, title, sum(1 for _, vetoed in on_the_ballot.get(pk, ()) if vetoed), film_points(on_the_ballot.get(pk, ())))
            for pk, title, _ in the_ballot
        ]
    )
    the_titles = {pk: title for pk, title, _ in the_ballot}
    the_runtimes = {pk: runtime for pk, _, runtime in the_ballot}
    broken = plan.breakdown(read, slate, {pk: runtime for pk, _, runtime in on_the_plan}, held, [each.key for each in ranked], records)
    return {
        "empty": not boxes,
        "film_lines": [
            {
                "title": titles[each.film],
                "runtime": each.runtime,
                "points": each.points,
                "most": each.most,
                "represents": [{"name": names[voter], "pins": pins} for voter, pins in each.represents],
                "likes": each.likes,
            }
            for each in broken.films
        ],
        "people": [
            {
                "name": names[each.voter],
                "film": titles.get(each.representative),
                "score": each.representation,
                "out": each.out,
                "pins": each.pins,
                "sum": each.slate_sum,
                "served": each.served,
                "best": None if each.best_eligible is None else {"title": the_titles[each.best_eligible[0]], "runtime": the_runtimes[each.best_eligible[0]], "score": each.best_eligible[1]},
            }
            for each in broken.people
        ],
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
