"""Every refusal the runtime parser can raise has the labelled box's own words (#138)."""

from ribcage.suggestions import runtime
from ribcage.timetable import labelling


def test_every_runtime_refusal_has_a_word_in_the_boxs_own():
    # The module's upper-case string constants are its refusals; LONGEST is an int and drops out.
    refusals = {value for name, value in vars(runtime).items() if name.isupper() and isinstance(value, str)}
    assert refusals
    assert set(labelling.IN_BOXS_WORDS) == refusals
