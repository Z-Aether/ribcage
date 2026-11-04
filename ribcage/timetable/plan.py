"""The slate ledger's rows as stored: the loader for the pure `readouts.ledger`, for Compare (#147, #164)."""

from dataclasses import dataclass

from django.conf import settings
from django.db.models import Exists, OuterRef, Q

from ribcage.ballot import floor as ballot_floor
from ribcage.ballot.board import candidates
from ribcage.ballot.models import BallotRecord
from ribcage.readouts import ledger, plan
from ribcage.readouts import swap as swapping
from ribcage.readouts.basis import NO_KNOBS, Basis, label
from ribcage.shortlist import keeping
from ribcage.suggestions.models import Suggestion
from ribcage.timetable import batch as batches
from ribcage.timetable import setting
from ribcage.timetable.models import Box

THE_PLAN = "The plan"
THIS_BATCH = "This batch"
SHORTLIST = "Shortlist"
SECTIONS = (THE_PLAN, SHORTLIST, THIS_BATCH)
NOTHING_YET = {THE_PLAN: "Nothing on the timetable yet.", SHORTLIST: "Nothing kept yet."}
NOTHING_TO_SOLVE = "nothing new to solve"


@dataclass(frozen=True)
class Wanted:
    """A further row for the ledger: its section, its label and its film set (suggestion ids); #165 and #169 pass theirs to `load`.

    `kept` is a kept proposal's key, which its row offers to discard, with its `provenance` line; a batch row `keeps` its film set unless it is `already_kept` (#169).
    """

    section: str
    label: str
    films: tuple
    kept: int = 0
    provenance: str = ""
    keeps: bool = False
    already_kept: bool = False


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
    stored = keeping.load()
    boxes = list(Box.objects.order_by("start", "pk").values_list("suggestion_id", flat=True))
    on_the_plan = [pk for pk in boxes if pk is not None]
    screen = set(on_the_plan).union(*(each.films for each in wanted), *(each.films for each in stored))
    votes = votes_under(screen, basis)
    ids, names, titles, on_the_ballot, stored_floor, vetoes, basis, found_floor, on = (votes.ids, votes.names, votes.titles, votes.on_the_ballot, votes.stored_floor, votes.vetoes, votes.basis, votes.found_floor, votes.on)

    # The batch answers to the votes loaded here on every render: it solves what the kept slates lack, and is never stored in the database (#17, #165, #166).
    found_batch = batches.propose(on, settings.FLOOR_WEIGHT_MULTIPLIER, rounds, kept, basis, titles) if solved else None
    already = {frozenset(each.films) for each in stored}
    proposals = [] if found_batch is None else [
        Wanted(THIS_BATCH, proposal_label(number, each), tuple(each), keeps=bool(each), already_kept=frozenset(each) in already) for number, each in enumerate(found_batch.slates, 1)
    ]
    # The kept proposals are scored live under the basis like every row; their provenance only explains (#17, #169).
    now = provenance(basis, ids, names, titles, on.candidates)
    kept_rows = [Wanted(SHORTLIST, f"Kept {number}", each.films, kept=each.pk, provenance=provenance_line(each.provenance, now)) for number, each in enumerate(stored, 1)]
    # An empty timetable is no row, so it joins no standing and no core (#147, #164).
    asked = [*([Wanted(THE_PLAN, THE_PLAN, tuple(on_the_plan))] if boxes else []), *wanted, *kept_rows, *proposals]
    floor_line = ballot_floor.line_of(found_floor, names)
    banners = {THIS_BATCH: {"floor_line": floor_line, "basis": basis_line(votes), "solved_in": f"solved in {found_batch.solved_ms} ms" if found_batch.solving else NOTHING_TO_SOLVE, "ending": found_batch.ending, "more": more_of(found_batch)}} if solved else {}
    memory = {"rounds": found_batch.rounds, "kept": found_batch.kept} if solved else {}
    knobs = knobs_of(basis, ids, names, dict(stored_floor.out), vetoes, on, titles)
    return {**of(asked, on, names, titles, banners=banners, pinned=basis.fixed_in, dropped=set(titles) - on_the_ballot, always=(THE_PLAN, SHORTLIST) if solved else (THE_PLAN,)), "empty": not boxes, "basis": basis, "knobs": knobs, **memory}


@dataclass(frozen=True)
class Votes:
    """What every row on screen is read against: the roster, the films' titles, the floor sets and the stored votes under the basis in force."""

    ids: tuple
    names: dict
    titles: dict
    on_the_ballot: set
    stored_floor: object
    vetoes: dict
    basis: Basis
    found_floor: object
    on: object


def votes_under(screen, basis):
    """The votes of the films in `screen` (suggestion ids) and the ballot's candidates under `basis`, in a fixed number of queries; the basis comes back cleaned (#164, #167, #170)."""
    ids, names = ballot_floor.roster()
    budget = setting.read().budget
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
    pins = basis.fixed_in & on_the_ballot
    basis = Basis(basis.without & set(ids), basis.disregarded & set(vetoes), pins, basis.fixed_out & on_the_ballot - pins)
    found_floor = ballot_floor.of_the_ballot(ids, runtimes, on_the_ballot, records, budget, basis.without, basis.fixed_out)
    on = ledger.stored_votes(ids, found_floor, records, titles, runtimes, on_the_ballot, budget, basis)
    return Votes(ids, names, titles, on_the_ballot, stored_floor, vetoes, basis, found_floor, on)


def swap_of(before, after, basis=Basis()):
    """The swap panel's data from the film sets `before` and `after` (suggestion ids) under `basis`, plain: a film no longer in the pool is left out of its side (#24, #170)."""
    votes = votes_under(set(before) | set(after), basis)
    left, right = (tuple(each for each in films if each in votes.titles) for films in (before, after))
    found = swapping.swap(left, right, votes.on)
    names, titles = votes.names, votes.titles
    pair = lambda one, two: {"before": one, "after": two}

    def film(each):
        return {"title": titles[each.film], "runtime": each.runtime, "points": each.points, "represents": [{"name": names[voter], "pins": pins} for voter, pins in each.represents]}

    def side(each):
        return {"film": titles.get(each.representative), "score": each.score, "pins": each.pins, "sum": each.slate_sum}

    return {
        "shared": [titles[each] for each in found.shared],
        "out": [titles[each] for each in found.out],
        "into": [titles[each] for each in found.into],
        "numbers": {
            "floor": pair(*found.floor),
            "sigma_rep": pair(*found.sigma_rep),
            "total": pair(*found.total),
            "screen_time": pair(*(plan.clock(each) for each in found.screen_time)),
        },
        "vetoes": {**pair(*found.vetoes), "delta": signed(found.vetoes[1] - found.vetoes[0])},
        "carried_out": [film(each) for each in found.carried_out],
        "carried_in": [film(each) for each in found.carried_in],
        "moves": [
            {"name": names[each.voter], "out": each.out, "before": side(each.before), "after": side(each.after), "change": each.change, "sum_change": each.sum_change}
            for each in found.moves
        ],
        "basis": basis_line(votes),
    }


def basis_line(votes):
    ids, names, titles, on = votes.ids, votes.names, votes.titles, votes.on
    return f"basis: {label(votes.basis, ids, names, on.candidates, titles)}" if votes.basis else NO_KNOBS


def provenance(basis, ids, names, titles, films=()):
    """The basis in words as a kept proposal stores it: the same for the same knobs, voters in the roster's order and films in key order (#169)."""
    return label(basis, ids, names, sorted(each for each in films if each in titles), titles)


def provenance_line(found, now):
    """What a kept row says of where it came from: the basis it was found under, and whether the row has been rescored since (#24, #169)."""
    return f"found under the current basis: {found}" if found == now else f"found under: {found} · rescored under the current basis"


def provenance_now(basis):
    """The words a keep stores for `basis`, as the session holds it: the knobs on voters or films since gone left out, as `load` leaves them (#169)."""
    ids, names = ballot_floor.roster()
    fixed = candidates().filter(pk__in=basis.fixed_in | basis.fixed_out)
    pins = set(fixed.values_list("pk", flat=True))
    titles = dict(fixed.values_list("pk", "title"))
    return provenance(Basis(basis.without & set(ids), basis.disregarded, basis.fixed_in & pins, basis.fixed_out & pins), ids, names, titles, pins)


def knobs_of(basis, ids, names, out_for, vetoes, on, titles):
    """The knob bar's data: a chip per voter to set aside, dimmed with the reason where the stored votes already leave them out, and one per vetoer with their veto count (#24, #167).

    A film is fixed in or out from a select of the candidates not already fixed, in slate order, each with a chip and its remove for the ones fixed (#168).
    """
    def film(each):
        return {"id": each, "title": titles[each], "runtime": on.runtimes[each]}

    free = [film(each) for each in on.candidates if each not in basis.fixed_in and each not in basis.fixed_out]
    return {
        "fix_in": {"options": free, "fixed": [film(each) for each in on.candidates if each in basis.fixed_in]},
        "fix_out": {"options": free, "fixed": [film(each) for each in on.candidates if each in basis.fixed_out]},
        "without": [{"id": each, "name": names[each], "on": each in basis.without, "reason": out_for.get(each, "")} for each in ids],
        "disregard": [{"id": each, "name": names[each], "on": each in basis.disregarded, "vetoes": vetoes[each]} for each in ids if each in vetoes],
        "any": bool(basis),
    }


def more_of(found):
    """The section header's count and "more": available until the cut stopped the chain, then greyed with the solver's reason (#17, #166)."""
    return {"count": len(found.slates), "available": not found.stopped, "reason": found.stopped}


def proposal_label(number, slate):
    return f"Proposal {number}" if slate else f"Proposal {number} (empty slate)"


def of(asked, on, names, titles, prefix="slate", banners=None, pinned=frozenset(), dropped=frozenset(), always=(THE_PLAN,)):
    """The ledger of `asked`, `Wanted` rows, over a `ledger.StoredVotes`: the one drawing, which the gallery calls over made-up data too.

    `banners` are a section's heading facts by name (#165); a banner's `more` is the header's count and "more" button (#166). `pinned` are the films fixed in, whose dots are outlined (#168). `dropped` are the films no longer on the ballot, marked on every row that holds one (#26 §5, #169); `always` are the sections drawn even when empty.
    """
    banners = banners or {}
    reads = [ledger.read(each.films, on) for each in asked]
    stood = ledger.standings([(each.plan.floor, each.plan.sigma_rep, each.total) for each in reads], on.floor_set.size, settings.FLOOR_WEIGHT_MULTIPLIER)
    shown = ledger.dots([each.films for each in reads], on.rank)
    rows = [
        {**row_of(one, stand, names, titles, on.runtimes, shown, pinned, dropped), "id": f"{prefix}-{number}", "label": each.label, **acts_of(each)}
        for number, (each, one, stand) in enumerate(zip(asked, reads, stood))
    ]
    sections = [
        {
            "name": name,
            "rows": [row for each, row in zip(asked, rows) if each.section == name],
            "empty": NOTHING_YET.get(name, ""),
            "banner": banners.get(name),
        }
        for name in SECTIONS
        if name in always or name in banners or any(each.section == name for each in asked)
    ]
    return {"columns": [{"id": film, "title": titles[film], "core": film in shown.core} for film in shown.columns], "sections": sections}


def acts_of(each):
    """What a row offers beside its figures: a batch row *keep*, or *kept* once its film set is on the shortlist, and a kept row *discard* with where it came from (#169)."""
    return {
        "keeping": "kept" if each.already_kept else "keep" if each.keeps else "",
        "film_ids": ",".join(str(pk) for pk in sorted(each.films)),
        "discard": each.kept,
        "provenance": each.provenance,
    }


def row_of(one, stand, names, titles, runtimes, shown, pinned=frozenset(), dropped=frozenset()):
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
        "dropped": [titles[film] for film in one.films if film in dropped],
        "screen_time": plan.clock(read.screen_time),
        "budget": None if read.budget is None else plan.clock(read.budget),
        "over": read.over,
        "dots": [{"id": film, "title": titles[film], "held": film in held, "core": film in shown.core, "fixed": film in pinned} for film in shown.columns],
        "people": [
            {"name": names[each.voter], "score": each.representation, "film": titles.get(each.representative), "out": each.out, "pins": each.pins} for each in read.rows
        ],
        "vetoes": len(read.vetoed),
        "vetoed": [{"film": titles[each.film], "by": [names[voter] for voter in each.vetoers]} for each in read.vetoed],
        "film_lines": [
            {
                "title": titles[each.film],
                "dropped": each.film in dropped,
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
