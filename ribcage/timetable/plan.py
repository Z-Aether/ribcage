"""The slate ledger's rows as stored: the loader for the pure `readouts.ledger`, for Compare (#147, #164)."""

from dataclasses import dataclass

from django.conf import settings
from django.db.models import Exists, OuterRef, Q

from ribcage.ballot import floor as ballot_floor
from ribcage.ballot.board import candidates
from ribcage.ballot.models import BallotRecord
from ribcage.readouts import ledger, plan
from ribcage.readouts.basis import NO_KNOBS, Basis, label
from ribcage.suggestions.models import Suggestion
from ribcage.timetable import batch as batches
from ribcage.timetable import setting
from ribcage.timetable.models import Box

THE_PLAN = "The plan"
THIS_BATCH = "This batch"
SECTIONS = (THE_PLAN, "Shortlist", THIS_BATCH)
NOTHING_YET = "Nothing on the timetable yet."
NOTHING_TO_SOLVE = "nothing new to solve"


@dataclass(frozen=True)
class Wanted:
    """A further row for the ledger: its section, its label and its film set (suggestion ids); #165 and #169 pass theirs to `load`."""

    section: str
    label: str
    films: tuple


def signed(distance):
    """A distance from the best row: = when level."""
    return "=" if not distance else f"{distance:+d}".replace("-", "\N{MINUS SIGN}")


def load(wanted=(), solved=False, rounds=1, kept=None, basis=Basis()):
    """The ledger as the page shows it, in a fixed number of queries however many rows and films: the plan's row, then each of `wanted`'s and, with `solved`, the batch's.

    `rounds` is how far "more" has taken it and `kept` what the last solve left for the batch to resume from; a solved ledger carries `rounds` and `kept` back for the session (#166).

    `basis` is the knobs the admin has set, which every row and the batch are scored under; a knob naming a voter no longer on the roster, or whose vetoes are gone, falls out,
    and the basis in force comes back as `basis` for the session, with the knob bar's data as `knobs` (#17, #167).

    The voters, the candidates', the rows' films and their ballot records are each loaded once for every row (#164).
    """
    ids, names = ballot_floor.roster()
    budget = setting.read().budget
    boxes = list(Box.objects.order_by("start", "pk").values_list("suggestion_id", flat=True))
    on_the_plan = [pk for pk in boxes if pk is not None]
    screen = set(on_the_plan).union(*(each.films for each in wanted))
    films = Suggestion.objects.filter(Q(pk__in=screen) | Q(pk__in=candidates().values("pk"))).annotate(on_the_ballot=Exists(candidates().filter(pk=OuterRef("pk"))))
    found = list(films.values_list("pk", "title", "runtime", "on_the_ballot"))
    titles = {pk: title for pk, title, _, _ in found}
    runtimes = {pk: runtime for pk, _, runtime, _ in found}
    on_the_ballot = {pk for pk, _, _, ballot in found if ballot}
    records = list(BallotRecord.objects.filter(suggestion__in=titles).values_list("voter_id", "suggestion_id", "score", "vetoed", "seen_it"))
    # The floor set reads the ballot alone; a dropped film's records on the plan count only for the plan's readouts (#26 §5).
    stored_floor = ballot_floor.of_the_ballot(ids, runtimes, on_the_ballot, records, budget)
    vetoes = {}
    for voter, film, _, vetoed, _ in records:
        if vetoed and film in on_the_ballot:
            vetoes[voter] = vetoes.get(voter, 0) + 1
    basis = Basis(basis.without & set(ids), basis.disregarded & set(vetoes))
    found_floor = ballot_floor.of_the_ballot(ids, runtimes, on_the_ballot, records, budget, basis.without)
    on = ledger.stored_votes(ids, found_floor, records, titles, runtimes, on_the_ballot, budget, basis)

    # The batch answers to the votes loaded here on every render: it solves what the kept slates lack, and is never stored in the database (#17, #165, #166).
    found_batch = batches.propose(on, settings.FLOOR_WEIGHT_MULTIPLIER, rounds, kept) if solved else None
    proposals = [] if found_batch is None else [Wanted(THIS_BATCH, proposal_label(number, each), tuple(each)) for number, each in enumerate(found_batch.slates, 1)]
    # An empty timetable is no row, so it joins no standing and no core (#147, #164).
    asked = [*([Wanted(THE_PLAN, THE_PLAN, tuple(on_the_plan))] if boxes else []), *wanted, *proposals]
    floor_line = ballot_floor.line_of(found_floor, names)
    banners = {THIS_BATCH: {"floor_line": floor_line, "basis": f"basis: {label(basis, ids, names)}" if basis else NO_KNOBS, "solved_in": f"solved in {found_batch.solved_ms} ms" if found_batch.solving else NOTHING_TO_SOLVE, "ending": found_batch.ending, "more": more_of(found_batch)}} if solved else {}
    memory = {"rounds": found_batch.rounds, "kept": found_batch.kept} if solved else {}
    knobs = knobs_of(basis, ids, names, dict(stored_floor.out), vetoes)
    return {**of(asked, on, names, titles, banners=banners), "empty": not boxes, "basis": basis, "knobs": knobs, **memory}


def knobs_of(basis, ids, names, out_for, vetoes):
    """The knob bar's data: a chip per voter to set aside, dimmed with the reason where the stored votes already leave them out, and one per vetoer with their veto count (#24, #167)."""
    return {
        "without": [{"id": each, "name": names[each], "on": each in basis.without, "reason": out_for.get(each, "")} for each in ids],
        "disregard": [{"id": each, "name": names[each], "on": each in basis.disregarded, "vetoes": vetoes[each]} for each in ids if each in vetoes],
        "any": bool(basis),
    }


def more_of(found):
    """The section header's count and "more": available until the cut stopped the chain, then greyed with the solver's reason (#17, #166)."""
    return {"count": len(found.slates), "available": not found.stopped, "reason": found.stopped}


def proposal_label(number, slate):
    return f"Proposal {number}" if slate else f"Proposal {number} (empty slate)"


def of(asked, on, names, titles, prefix="slate", banners=None):
    """The ledger of `asked`, `Wanted` rows, over a `ledger.StoredVotes`: the one drawing, which the gallery calls over made-up data too.

    `banners` are a section's heading facts by name (#165); a banner's `more` is the header's count and "more" button (#166).
    """
    banners = banners or {}
    reads = [ledger.read(each.films, on) for each in asked]
    stood = ledger.standings([(each.plan.floor, each.plan.sigma_rep, each.total) for each in reads], on.floor_set.size, settings.FLOOR_WEIGHT_MULTIPLIER)
    shown = ledger.dots([each.films for each in reads], on.rank)
    rows = [
        {**row_of(one, stand, names, titles, on.runtimes, shown), "id": f"{prefix}-{number}", "label": each.label}
        for number, (each, one, stand) in enumerate(zip(asked, reads, stood))
    ]
    sections = [
        {
            "name": name,
            "rows": [row for each, row in zip(asked, rows) if each.section == name],
            "empty": NOTHING_YET if name == THE_PLAN else "",
            "banner": banners.get(name),
        }
        for name in SECTIONS
        if name == THE_PLAN or name in banners or any(each.section == name for each in asked)
    ]
    return {"columns": [{"title": titles[film], "core": film in shown.core} for film in shown.columns], "sections": sections}


def row_of(one, stand, names, titles, runtimes, shown):
    """One row's data for `components/slate_row.html`, plain."""
    read = one.plan
    if stand.best:
        says = "best on screen"
    else:
        says = "tied with the best" if stand.level else ""
    held = set(one.films)
    return {
        "tier": stand.tier,
        "tied": stand.tied,
        "standing": says,
        "floor": read.floor,
        "floor_distance": None if stand.floor_distance is None else signed(stand.floor_distance),
        "sigma_rep": read.sigma_rep,
        "sigma_distance": signed(stand.sigma_distance),
        "total": one.total,
        "films": read.films,
        "screen_time": plan.clock(read.screen_time),
        "budget": None if read.budget is None else plan.clock(read.budget),
        "over": read.over,
        "dots": [{"title": titles[film], "held": film in held, "core": film in shown.core} for film in shown.columns],
        "people": [
            {"name": names[each.voter], "score": each.representation, "film": titles.get(each.representative), "out": each.out, "pins": each.pins} for each in read.rows
        ],
        "vetoes": len(read.vetoed),
        "vetoed": [{"film": titles[each.film], "by": [names[voter] for voter in each.vetoers]} for each in read.vetoed],
        "film_lines": [
            {
                "title": titles[each.film],
                "runtime": each.runtime,
                "points": each.points,
                "most": each.most,
                "represents": [{"name": names[voter], "pins": pins} for voter, pins in each.represents],
                "likes": each.likes,
            }
            for each in one.breakdown.films
        ],
        "breakdown_people": [
            {
                "name": names[each.voter],
                "film": titles.get(each.representative),
                "score": each.representation,
                "out": each.out,
                "pins": each.pins,
                "sum": each.slate_sum,
                "served": each.served,
                "best": None if each.best_eligible is None else {"title": titles[each.best_eligible[0]], "runtime": runtimes[each.best_eligible[0]], "score": each.best_eligible[1]},
            }
            for each in one.breakdown.people
        ],
    }
