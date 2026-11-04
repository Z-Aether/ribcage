"""The knobs' arithmetic over plain data: the trap catalogue's knob traps (#17, #25, #33, #167)."""

import itertools

from ribcage.readouts.basis import NO_KNOBS, Basis, label, under
from ribcage.readouts.floor import SET_ASIDE, floor_set
from ribcage.readouts.ledger import read, stored_votes
from ribcage.solver.model import solve
from ribcage.solver.objective import Problem, scale_of, value

TITLES = {"cube": "Cube", "thing": "The Thing", "alien": "Alien"}
RUNTIMES = {"cube": 90, "thing": 109, "alien": 117}
RECORDS = [
    ("ada", "cube", 3, False, False),
    ("ada", "thing", 1, False, False),
    ("dani", "thing", 2, False, False),
    ("dani", "cube", None, True, False),
    ("eszter", "alien", 3, False, False),
]
VOTERS = ("ada", "dani", "eszter")


def votes(basis, budget=None):
    found = floor_set(VOTERS, RUNTIMES, RECORDS, budget, basis.without)
    return stored_votes(VOTERS, found, RECORDS, TITLES, RUNTIMES, set(TITLES), budget, basis)


def problem(basis, budget=None):
    on = votes(basis, budget)
    return Problem(on.voters, RUNTIMES, on.records, budget, on.floor_set, 1)


def points(result):
    return {line.film: line.points for line in result.breakdown.films}


def test_disregarding_a_voters_vetoes_scores_their_vetoed_films_zero_not_minus_two_in_the_total_and_the_film_points():
    stored = read(["cube", "thing"], votes(Basis()))
    disregarded = read(["cube", "thing"], votes(Basis(disregarded=frozenset({"dani"}))))

    assert (points(stored)["cube"], stored.total) == (3 - 2, 1 + 3)
    assert (points(disregarded)["cube"], disregarded.total) == (3, 3 + 3)


def test_the_vetoes_still_bar_those_films_from_representing_the_voter_who_stays_in_the_floor_set():
    basis = Basis(disregarded=frozenset({"dani"}))
    records = [("dani", "cube", 3, False, False), ("dani", "thing", None, True, False)]
    on = stored_votes(("dani",), floor_set(("dani",), RUNTIMES, records, None), records, TITLES, RUNTIMES, set(TITLES), None, basis)
    result = read(["thing"], on)

    assert on.floor_set.members == ("dani",)
    assert result.plan.rows[0].representative is None
    assert [(each.vetoers) for each in result.plan.vetoed] == [("dani",)]


def test_the_stored_records_are_left_as_they_were_and_a_disregarded_veto_is_marked_in_the_copy():
    held = list(RECORDS)

    counted = under(held, Basis(disregarded=frozenset({"dani"})))

    assert held == RECORDS
    assert counted[3][3] and counted[3][3] is not True
    assert counted[0] == RECORDS[0]


def test_without_a_voter_removes_them_from_the_floor_sigma_rep_and_the_total():
    result = read(["cube", "thing", "alien"], votes(Basis(without=frozenset({"ada"}))))
    stored = read(["cube", "thing", "alien"], votes(Basis()))

    assert [(each.voter, each.out) for each in result.plan.rows if each.out] == [("ada", SET_ASIDE)]
    assert result.plan.sigma_rep == stored.plan.sigma_rep - 3
    assert result.total == stored.total - (3 + 1)
    assert all(each.slate_sum is None for each in result.breakdown.people if each.voter == "ada")


def test_the_floor_set_reads_set_aside_by_knob_whatever_else_would_keep_them_out():
    found = floor_set(VOTERS, RUNTIMES, [*RECORDS, ("fay", "cube", 2, False, True)], None, {"ada", "fay"})

    assert dict(floor_set(("fay",), RUNTIMES, [("fay", "cube", 2, False, True)], None, {"fay"}).out) == {"fay": SET_ASIDE}
    assert dict(found.out) == {"ada": SET_ASIDE}
    assert found.members == ("dani", "eszter")


def test_the_slate_order_stays_on_the_stored_votes_whatever_the_basis():
    stored = votes(Basis())
    knobbed = votes(Basis(without=frozenset({"ada", "dani"}), disregarded=frozenset({"dani"})))

    assert knobbed.rank == stored.rank and knobbed.candidates == stored.candidates


def test_k_still_exceeds_twice_the_largest_total_under_each_knob():
    for basis in (Basis(), Basis(without=frozenset({"ada"})), Basis(disregarded=frozenset({"dani"})), Basis(frozenset({"eszter"}), frozenset({"dani"}))):
        given = problem(basis)
        totals = [abs(value(films, given).total) for size in range(4) for films in itertools.combinations(RUNTIMES, size)]

        assert scale_of(given) > 2 * max(totals)


def test_a_disregarded_veto_adds_nothing_to_the_bound_and_a_set_aside_voter_nothing_at_all():
    assert scale_of(problem(Basis())) == 2 * (3 + 1 + 2 + 2 + 3) + 1
    assert scale_of(problem(Basis(disregarded=frozenset({"dani"})))) == 2 * (3 + 1 + 2 + 3) + 1
    assert scale_of(problem(Basis(without=frozenset({"dani"})))) == 2 * (3 + 1 + 3) + 1


def test_the_solver_takes_a_voter_out_of_the_floor_and_the_totals():
    # Alone, eszter's alien is all that is worth proposing for the floor; with ada and dani set aside nothing else counts.
    given = problem(Basis(without=frozenset({"ada", "dani"})), budget=120)

    assert solve(given) == {"alien"}
    assert given.floor_set.members == ("eszter",)


def test_the_solver_scores_a_disregarded_veto_zero_so_the_vetoed_film_can_win_on_the_total():
    # ada is represented 2 by either film, so the total alone decides: dani's veto of cube tips it to thing unless it is disregarded.
    records = [
        ("ada", "cube", 2, False, False), ("ada", "thing", 2, False, False), ("dani", "cube", None, True, False), ("dani", "thing", 0, False, False), ("eszter", "cube", 1, False, True),
    ]  # fmt: skip
    runtimes = {"cube": 100, "thing": 100}
    voters = ("ada", "dani", "eszter")

    def best(basis):
        found = floor_set(voters, runtimes, records, 100, basis.without)
        return solve(Problem(voters, runtimes, under(records, basis), 100, found, 1))

    assert best(Basis()) == {"thing"}
    assert best(Basis(disregarded=frozenset({"dani"}))) == {"cube"}


def test_the_basis_line_names_each_knob_in_the_roster_order_or_says_no_knobs():
    names = {"ada": "Ada", "dani": "Dani", "eszter": "Eszter"}

    assert label(Basis(), VOTERS, names) == NO_KNOBS
    assert label(Basis(frozenset({"dani"}), frozenset({"eszter"})), VOTERS, names) == "without Dani · Eszter's vetoes disregarded"
    assert label(Basis(frozenset({"dani", "ada"})), VOTERS, names) == "without Ada, Dani"
