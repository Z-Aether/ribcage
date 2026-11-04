"""The film knobs' arithmetic over plain data: fix a film in or out (#17, #33, #168)."""

from ribcage.readouts.basis import NO_KNOBS, Basis, label
from ribcage.readouts.floor import NOTHING_REPRESENTABLE, floor_set
from ribcage.readouts.ledger import stored_votes
from ribcage.solver.model import solve
from ribcage.solver.objective import Problem, scale_of
from ribcage.timetable import batch

TITLES = {"cube": "Cube", "thing": "The Thing", "alien": "Alien", "coco": "Coco"}
RUNTIMES = {"cube": 90, "thing": 109, "alien": 117, "coco": 105}
RECORDS = [
    ("ada", "cube", 3, False, False),
    ("ada", "thing", 1, False, False),
    ("dani", "thing", 2, False, False),
    ("eszter", "alien", 3, False, False),
    ("eszter", "coco", 1, False, False),
]
VOTERS = ("ada", "dani", "eszter")


def on_the(basis, budget=None):
    found = floor_set(VOTERS, RUNTIMES, RECORDS, budget, basis.without, basis.fixed_out)
    return stored_votes(VOTERS, found, RECORDS, TITLES, RUNTIMES, set(TITLES), budget, basis)


def proposed(basis, budget=None, rounds=1):
    return batch.propose(on_the(basis, budget), 1, rounds, None, basis, TITLES)


def test_a_fixed_in_film_is_in_every_proposal_of_the_batch_and_a_fixed_out_film_in_none(settings):
    settings.DIVERSITY_CUT, settings.BATCH_SIZE = 1, 4
    free = proposed(Basis(), 250)
    pinned = proposed(Basis(fixed_in=frozenset({"coco"})), 250)
    barred = proposed(Basis(fixed_out=frozenset({"alien"})), 250)

    assert any("coco" not in each for each in free.slates)
    assert len(pinned.slates) > 1 and all("coco" in each for each in pinned.slates)
    assert len(barred.slates) > 1 and all("alien" not in each for each in barred.slates)


def test_a_fixed_film_counts_toward_the_budget_like_any_other():
    only = proposed(Basis(fixed_in=frozenset({"alien"})), 200)

    assert "alien" in only.slates[0] and sum(RUNTIMES[each] for each in only.slates[0]) <= 200


def test_the_floor_set_treats_a_fixed_out_film_as_not_representable():
    # eszter keeps coco unless it goes too; dani's only film is thing.
    assert floor_set(VOTERS, RUNTIMES, RECORDS, None, fixed_out={"alien", "coco"}).out == (("eszter", NOTHING_REPRESENTABLE),)
    assert floor_set(VOTERS, RUNTIMES, RECORDS, None, fixed_out={"alien"}).members == VOTERS
    assert dict(floor_set(VOTERS, RUNTIMES, RECORDS, None, fixed_out={"thing"}).out) == {"dani": NOTHING_REPRESENTABLE}
    assert floor_set(VOTERS, RUNTIMES, RECORDS, None, fixed_out={"cube", "thing"}).out == (("ada", NOTHING_REPRESENTABLE), ("dani", NOTHING_REPRESENTABLE))


def test_a_fixed_in_film_crowding_out_a_voters_only_film_is_not_caught_by_the_floor_set():
    found = floor_set(VOTERS, RUNTIMES, RECORDS, 130)

    assert found.members == VOTERS


def test_k_ranges_over_the_candidates_not_fixed_out():
    stored = batch.problem_of(on_the(Basis()), 1)
    barred = batch.problem_of(on_the(Basis(fixed_out=frozenset({"alien"}))), 1, Basis(fixed_out=frozenset({"alien"})))

    assert "alien" not in barred.runtimes
    assert scale_of(barred) == scale_of(stored) - 2 * 3


def test_pins_over_the_budget_give_no_proposal_and_name_the_pins_with_their_runtimes():
    basis = Basis(fixed_in=frozenset({"alien", "thing", "coco"}))
    result = proposed(basis, 200)

    assert result.slates == ()
    assert result.ending == "The films fixed in alone exceed the budget: Alien (117m), The Thing (109m), Coco (105m). Nothing dropped."
    assert solve(batch.problem_of(on_the(basis, 200), 1, basis)) is None


def test_the_pins_are_named_in_slate_order_and_a_feasible_pin_set_has_no_such_ending():
    assert proposed(Basis(fixed_in=frozenset({"alien"})), 200).ending == ""


def test_fixing_a_film_in_clears_its_fix_out_and_the_other_way():
    out = Basis().fixing("coco", "fixed_out", True)

    assert out.fixed_out == {"coco"}
    assert out.fixing("coco", "fixed_in", True) == Basis(fixed_in=frozenset({"coco"}))
    assert out.fixing("coco", "fixed_out", False) == Basis()
    assert out.fixing("alien", "fixed_in", False) == out


def test_the_basis_line_names_the_films_after_the_voters():
    names = {"ada": "Ada", "dani": "Dani", "eszter": "Eszter"}
    basis = Basis(frozenset({"dani"}), fixed_in=frozenset({"alien"}), fixed_out=frozenset({"coco", "cube"}))

    assert label(basis, VOTERS, names, ["cube", "alien", "coco"], TITLES) == "without Dani · Alien fixed in · Cube, Coco fixed out"
    assert label(Basis(), VOTERS, names, ["cube"], TITLES) == NO_KNOBS


def test_a_different_pin_is_a_different_problem_so_the_kept_slates_are_dropped(settings):
    first = proposed(Basis(), 250)
    pinned_basis = Basis(fixed_in=frozenset({"coco"}))
    again = batch.propose(on_the(pinned_basis, 250), 1, 2, first.kept, pinned_basis, TITLES)

    assert again.rounds == 1
