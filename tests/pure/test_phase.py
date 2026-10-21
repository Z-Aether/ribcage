import pytest

from ribcage.phase.order import PHASES, MoveRefused, Neighbours, Phase, check_move, derived_phase, neighbours

SUGGEST, APPROVE, VOTE, PICK, RUN = Phase


def test_the_order_is_the_glossarys_five_phases_in_order():
    assert PHASES == ["SUGGEST", "APPROVE", "VOTE", "PICK", "RUN"]


def test_with_no_history_the_phase_is_suggest():
    assert derived_phase([]) is SUGGEST


def test_after_a_forward_walk_the_phase_is_the_last_one_entered():
    assert derived_phase(["APPROVE", "VOTE", "PICK", "RUN"]) is RUN


def test_after_a_backward_walk_the_phase_is_the_last_one_entered():
    assert derived_phase(["APPROVE", "VOTE", "PICK", "VOTE", "APPROVE"]) is APPROVE


def test_walking_back_to_the_start_returns_to_suggest():
    assert derived_phase(["APPROVE", "SUGGEST"]) is SUGGEST


@pytest.mark.parametrize(
    ("phase", "expected"),
    [
        (SUGGEST, Neighbours(back=None, forward=APPROVE)),
        (APPROVE, Neighbours(back=SUGGEST, forward=VOTE)),
        (VOTE, Neighbours(back=APPROVE, forward=PICK)),
        (PICK, Neighbours(back=VOTE, forward=RUN)),
        (RUN, Neighbours(back=PICK, forward=None)),
    ],
)
def test_each_phase_has_one_step_back_and_one_forward_with_none_before_suggest_or_after_run(phase, expected):
    assert neighbours(phase) == expected


ONE_STEP_FORWARD = list(zip(PHASES, PHASES[1:]))
ONE_STEP_BACK = [(after, before) for before, after in ONE_STEP_FORWARD]


@pytest.mark.parametrize(("from_phase", "to_phase"), ONE_STEP_FORWARD + ONE_STEP_BACK)
def test_a_move_one_step_either_way_is_allowed(from_phase, to_phase):
    check_move(from_phase, from_phase, to_phase)


@pytest.mark.parametrize(
    ("from_phase", "to_phase"),
    [(SUGGEST, VOTE), (SUGGEST, RUN), (RUN, SUGGEST), (PICK, APPROVE), (VOTE, VOTE), (SUGGEST, None), (RUN, None)],
)
def test_a_move_to_anything_but_a_neighbour_is_refused(from_phase, to_phase):
    with pytest.raises(MoveRefused):
        check_move(from_phase, from_phase, to_phase)


@pytest.mark.parametrize("to_phase", ["SETUP", "vote", ""])
def test_a_move_to_a_phase_that_does_not_exist_is_refused(to_phase):
    with pytest.raises(MoveRefused):
        check_move(APPROVE, APPROVE, to_phase)


def test_a_move_from_a_phase_that_is_not_current_is_refused_even_one_step_from_it():
    with pytest.raises(MoveRefused, match="The phase is VOTE, not APPROVE"):
        check_move(VOTE, APPROVE, VOTE)
