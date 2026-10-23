"""A runtime as a voter types it: positive whole minutes, refused gently and never coerced (#21, #90)."""

import pytest

from ribcage.films import card
from ribcage.identity.models import Voter
from ribcage.phase.order import Phase
from ribcage.suggestions import runtime
from ribcage.suggestions.models import Approval, Suggestion, as_suggested
from ribcage.suggestions.pool import film_card
from tests.films import THE_SHINING

ADA = Voter(pk=1, display_name="Ada")
BO = Voter(pk=2, display_name="Bo")


@pytest.mark.parametrize(("typed", "minutes"), [("144", 144), (" 171 ", 171), ("1", 1), ("0090", 90), ("32767", 32767), ("0" * 5000 + "144", 144)])
def test_whole_minutes_are_read_as_typed(typed, minutes):
    assert runtime.minutes(typed) == minutes


@pytest.mark.parametrize(
    ("typed", "said"),
    [
        pytest.param("", runtime.EMPTY, id="blank"),
        pytest.param("   ", runtime.EMPTY, id="spaces"),
        pytest.param("0", runtime.NOT_POSITIVE, id="zero"),
        pytest.param("-5", runtime.NOT_POSITIVE, id="negative"),
        pytest.param("90.5", runtime.NOT_WHOLE_MINUTES, id="a decimal"),
        pytest.param("90.0", runtime.NOT_WHOLE_MINUTES, id="a whole decimal"),
        pytest.param("90,5", runtime.NOT_WHOLE_MINUTES, id="a decimal comma"),
        pytest.param("1h 30", runtime.NOT_WHOLE_MINUTES, id="hours"),
        pytest.param("2:31", runtime.NOT_WHOLE_MINUTES, id="a clock"),
        pytest.param("144 min", runtime.NOT_WHOLE_MINUTES, id="a unit"),
        pytest.param("1e3", runtime.NOT_WHOLE_MINUTES, id="an exponent"),
        pytest.param("١٤٤", runtime.NOT_WHOLE_MINUTES, id="other digits"),
        pytest.param("32768", runtime.TOO_LONG, id="past the field"),
        pytest.param("9" * 5000, runtime.TOO_LONG, id="past any int"),
        pytest.param("0" * 5000, runtime.NOT_POSITIVE, id="a run of zeros"),
    ],
)
def test_anything_but_positive_whole_minutes_is_refused_with_a_gentle_word(typed, said):
    with pytest.raises(runtime.Refused) as refused:
        runtime.minutes(typed)

    assert str(refused.value) == said



# The pencil on the card


def a_suggestion(approval=Approval.UNDECIDED):
    return Suggestion(pk=10, suggester=ADA, suggester_name="Ada", approval=approval, **as_suggested(THE_SHINING))


@pytest.mark.parametrize("viewer", [ADA, BO], ids=["the suggester", "another voter"])
@pytest.mark.parametrize("approval", [Approval.UNDECIDED, Approval.DROPPED])
def test_in_suggest_any_voter_is_offered_the_pencil_on_a_withdrawable_film(viewer, approval):
    assert film_card(a_suggestion(approval), [], viewer, Phase.SUGGEST).runtime_pencil == card.RuntimePencil()


def test_the_card_offers_no_pencil_on_an_approved_film():
    assert film_card(a_suggestion(Approval.APPROVED), [], BO, Phase.SUGGEST).runtime_pencil is None


@pytest.mark.parametrize("phase", [Phase.APPROVE, Phase.VOTE, Phase.PICK, Phase.RUN])
def test_the_card_offers_no_pencil_outside_suggest(phase):
    assert film_card(a_suggestion(), [], BO, phase).runtime_pencil is None


def test_without_a_viewer_the_card_offers_no_pencil():
    assert film_card(a_suggestion(), []).runtime_pencil is None
