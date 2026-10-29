from datetime import date

import pytest

from ribcage.seeding.timetable import next_saturday

SATURDAY = date(2026, 11, 7)


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 11, 2), SATURDAY),  # a Monday
        (date(2026, 11, 5), SATURDAY),  # Thursday: two days out
        (date(2026, 11, 6), date(2026, 11, 14)),  # Friday: tomorrow is too soon
        (SATURDAY, date(2026, 11, 14)),
        (date(2026, 11, 8), date(2026, 11, 14)),
    ],
)
def test_the_seeded_saturday_is_at_least_two_days_out(today, expected):
    assert next_saturday(today) == expected
