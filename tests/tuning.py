"""The diversity cut's second tuning stage: how long each answer on Compare takes at k = 2, 3 and 4, on the seed corpus (#17, #25, #174), and under each tiebreaker rule at k = 2 (#176).

Run `python -m tests.tuning` from the repo root. It reads the past marathons' votes in `private/past-marathons/` when that directory is there, and the seeded ballots (#50) always.
Each instance is a letter (A, B, C ... for the past marathons in file order, S for the seeded ballots), in the output as everywhere; nothing from `private/` is printed or written outside `tmp/`.
A measurement, not a test: `tests/pure/test_tuning.py` holds the mapping and the skip, and the timings go to `tmp/m9/176-timings.json`.

The films are the seed corpus's fifty with their runtimes; a vote on a film the corpus lacks is left out, and so is a blank.
A voter's ranking maps onto -1..+3 in five even bands down the ranked films (the top fifth +3, the bottom fifth -1), and an X is a veto (#174).
The "whole render" is the batch plus the ledger's drawing of its rows over plain data, which is what `timetable.plan.load` does but for its queries.
"""

import csv
import json
import re
import sys
import time
from dataclasses import replace
from pathlib import Path

from ribcage.readouts import tiebreaker
from tests.oracle import Instance, votes_of

ROOT = Path(__file__).resolve().parent.parent
PAST_MARATHONS = ROOT / "private" / "past-marathons"
TIMINGS = ROOT / "tmp" / "m9" / "176-timings.json"
KS = (2,)  # #174 measured 3 and 4: both bite
RULES = tuple(tiebreaker.KEYS)
BUDGETS = (8, 12, 16, 20, 24, None)
KNOB_KINDS = ("none", "without", "disregarded", "fixed_in", "fixed_out")
MORES = 3
BITES_AFTER_SECONDS = 3
BANDS = (3, 2, 1, 0, -1)


def scores_from_ranking(ranks):
    """A voter's scores from their ranks (1 is best; None a blank, "X" a veto), by film: (score, vetoed) for each film they ranked or vetoed, none for a blank.

    The ranked films fall into `BANDS` by place, evenly, tied ranks sharing the place of the first (#174).
    """
    ranked = sorted((rank, film) for film, rank in ranks.items() if isinstance(rank, int))
    count = len(ranked)
    placed = {}
    first = {}
    for place, (rank, film) in enumerate(ranked):
        first.setdefault(rank, place)
        placed[film] = BANDS[len(BANDS) * first[rank] // count]
    found = {film: (placed[film], False) for film in placed}
    found.update({film: (None, True) for film, rank in ranks.items() if rank == "X"})
    return found


def plain(title):
    return re.sub(r"\W+", " ", title.casefold()).strip()


def split_title(written):
    found = re.match(r"(.*?)\s*\((\d{4})\)\s*$", written.strip())
    return (found[1], int(found[2])) if found else (written.strip(), None)


def match_title(written, entries):
    """The index in `entries` (corpus entries) of the film written, by title and year, else by title alone where one entry has it; None where none does."""
    title, year = split_title(written)
    same = [place for place, each in enumerate(entries) if plain(each.written_title) == plain(title)]
    for place in same:
        if entries[place].written_year == year:
            return place
    return same[0] if len(same) == 1 else None


def read_ranks(path):
    """One year's file as (voter columns, [(title as written, [rank per voter])]), a rank being a whole number, "X" or None."""
    rows = list(csv.reader(Path(path).read_text(encoding="utf-8-sig").splitlines()))
    films = []
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        cells = [each.strip() for each in row[1:]]
        films.append((row[0], [int(each) if each.isdigit() else "X" if each.upper() == "X" else None for each in cells]))
    return len(rows[0]) - 1, films


def instance_from(name, voters, films, entries, runtimes):
    """The instance for one year's ranks: each voter's ranking mapped on the scale, the films matched to `entries` and the rest left out."""
    people = tuple(f"{name}{number}" for number in range(1, voters + 1))
    matched = [(match_title(title, entries), ranks) for title, ranks in films]
    records = []
    for number, voter in enumerate(people):
        scored = scores_from_ranking({place: ranks[number] for place, (_, ranks) in enumerate(matched)})
        for place, (key, _) in enumerate(matched):
            if key is not None and place in scored:
                score, vetoed = scored[place]
                records.append((voter, key, score, vetoed, False))
    return Instance(name, people, dict(runtimes), tuple(records), None)


def corpus_films():
    from ribcage.films import corpus

    read = corpus.read_corpus()
    return [each.entry for each in read], {number: each.film.runtime for number, each in enumerate(read)}, {number: each.film.title for number, each in enumerate(read)}


def past_instances(directory=PAST_MARATHONS, corpus=None):
    """One instance per `votes_*.csv` in `directory`, lettered A, B ... in file order; none where the directory is missing, which is how the harness skips without `private/` (#174)."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    entries, runtimes, _ = corpus or corpus_films()
    found = []
    for letter, path in zip("ABCDEFGH", sorted(directory.glob("votes_*.csv"))):
        voters, films = read_ranks(path)
        found.append(instance_from(letter, voters, films, entries, runtimes))
    return found


def seeded_instance(corpus=None):
    """The seeded ballots (#50) on the corpus's fifty films."""
    from ribcage.seeding import ballots

    entries, runtimes, _ = corpus or corpus_films()
    key = {each.tmdb_id: number for number, each in enumerate(entries) if each.tmdb_id}
    records = {}
    for voter, scores in ballots.SEEDED_SCORES.items():
        for film, score in scores.items():
            records[voter, key[film]] = [score, False, False]
    for voter, vetoes in ballots.SEEDED_VETOES.items():
        for film in vetoes:
            records.setdefault((voter, key[film]), [None, False, False])[1] = True
    for voter, films in ballots.SEEDED_SEEN.items():
        for film in films:
            records.setdefault((voter, key[film]), [None, False, False])[2] = True
    voters = tuple(dict.fromkeys([*ballots.SEEDED_SCORES, *ballots.SEEDED_VETOES, *ballots.SEEDED_SEEN, "Bartholomew Winthrop"]))
    return Instance("S", voters, dict(runtimes), tuple((voter, film, *each) for (voter, film), each in records.items()), None)


def with_knob(instance, kind, budget):
    """`instance` at `budget` hours (None for no budget) with one knob of `kind`: the first voter set aside, the voter with most vetoes disregarded, the best-ranked film fixed out, the second fixed in."""
    base = replace(instance, budget=None if budget is None else budget * 60)
    on, _ = votes_of(base)
    if kind == "without":
        return replace(base, without=(base.voters[0],))
    if kind == "disregarded":
        vetoes = {voter: sum(1 for each in base.records if each[0] == voter and each[3]) for voter in base.voters}
        return replace(base, disregarded=(max(base.voters, key=lambda voter: vetoes[voter]),))
    if kind == "fixed_out":
        return replace(base, fixed_out=(on.candidates[0],))
    if kind == "fixed_in":
        return replace(base, fixed_in=(on.candidates[1],))
    return base


def answers(instance, k, rule=tiebreaker.DEFAULT):
    """The admin's waits for `instance` at `k` under the tiebreaker `rule`: opening Compare, then up to `MORES` presses of "more", each as (answer, solve ms, whole render ms, slates held).

    Each press resumes from what the last render kept, as the session does (#166), so a press times only the round it solves.
    """
    from django.test import override_settings

    from ribcage.timetable import batch, plan

    on, basis = votes_of(instance)
    names = {voter: voter for voter in instance.voters}
    titles = {film: str(film) for film in instance.runtimes}
    out, kept = [], None
    with override_settings(DIVERSITY_CUT=k, SLATE_TIEBREAKER=rule):
        for rounds in range(1, MORES + 2):
            started = time.perf_counter()
            found = batch.propose(on, instance.multiplier, rounds, kept, basis, titles)
            solved = time.perf_counter() - started
            asked = [plan.Wanted(plan.THIS_BATCH, f"Proposal {number}", tuple(each)) for number, each in enumerate(found.slates, 1)]
            plan.of(asked, on, names, titles, banners={plan.THIS_BATCH: {}})
            whole = time.perf_counter() - started
            out.append(("open" if rounds == 1 else f"more {rounds - 1}", round(solved * 1000), round(whole * 1000), len(found.slates), bool(found.stopped)))
            kept = found.kept
    return out


def reading(instance, k, rule=tiebreaker.DEFAULT):
    """The batch at the default floor weight (c = 1) as counts only: per proposal its films, hours, films shared with the first and fewest films from any earlier one."""
    from django.test import override_settings

    from ribcage.timetable import batch
    from ribcage.solver.objective import value

    on, basis = votes_of(instance)
    given = batch.problem_of(on, 1, basis, rule)
    with override_settings(DIVERSITY_CUT=k):
        slates, _ = batch.chain(given, 5, k)
    lines = []
    for place, each in enumerate(slates):
        apart = min((len(each ^ other) for other in slates[:place]), default=None)
        lines.append(
            {
                "films": len(each),
                "hours": round(sum(given.runtimes[film] for film in each) / 60, 1),
                "shared_with_first": len(each & slates[0]),
                "fewest_apart": apart,
                "triple": list(value(each, given).triple),
            }
        )
    return lines


def measure(instances, ks=KS, rules=RULES, report=print):
    rows = []
    for instance in instances:
        for rule in rules:
            for k in ks:
                for budget in BUDGETS:
                    for kind in KNOB_KINDS:
                        for answer, solved, whole, held, stopped in answers(with_knob(instance, kind, budget), k, rule):
                            rows.append(
                                {"instance": instance.name, "rule": rule, "k": k, "budget": budget, "knob": kind, "answer": answer, "solve_ms": solved, "render_ms": whole, "slates": held, "stopped": stopped}
                            )
                report(f"instance {instance.name} {rule} done")
    return rows


def summarise(rows, report=print):
    """Per rule and k: the worst whole render and how many bite, then per instance letter its worst and median render, and per answer its median and worst."""
    for rule in sorted({each["rule"] for each in rows}):
        for k in sorted({each["k"] for each in rows}):
            mine = [each for each in rows if each["rule"] == rule and each["k"] == k]
            worst = max(mine, key=lambda each: each["render_ms"])
            over = [each for each in mine if each["render_ms"] > BITES_AFTER_SECONDS * 1000]
            report(
                f"{rule} k={k}: {len(mine)} answers, worst render {worst['render_ms']} ms ({worst['instance']}, budget {worst['budget']}, knob {worst['knob']}, {worst['answer']}), over {BITES_AFTER_SECONDS} s: {len(over)}"
            )
            for letter in sorted({each["instance"] for each in mine}):
                times = sorted(each["render_ms"] for each in mine if each["instance"] == letter)
                report(f"  {letter}: median {times[len(times) // 2]} ms, worst {times[-1]} ms")
            for answer in sorted({each["answer"] for each in mine}):
                times = sorted(each["render_ms"] for each in mine if each["answer"] == answer)
                report(f"  {answer}: median {times[len(times) // 2]} ms, worst {times[-1]} ms")


def main(argv):
    directory = Path(argv[0]) if argv else PAST_MARATHONS
    import django

    sys.path.insert(0, str(ROOT))
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
    django.setup()
    corpus = corpus_films()
    instances = [*past_instances(directory, corpus), seeded_instance(corpus)]
    if len(instances) == 1:
        print("no past marathons found; measuring the seeded ballots alone")
    rows = measure(instances)
    TIMINGS.parent.mkdir(parents=True, exist_ok=True)
    TIMINGS.write_text(json.dumps(rows))
    summarise(rows)
    for instance in instances:
        for rule in RULES:
            for k in KS:
                print(f"batch {instance.name} {rule} k={k} at 16 h, no knobs:", reading(with_knob(instance, "none", 16), k, rule))


if __name__ == "__main__":
    main(sys.argv[1:])
