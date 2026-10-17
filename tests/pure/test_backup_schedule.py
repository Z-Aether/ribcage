from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from ribcage.operations.backup import (
    KEPT_BACKUPS,
    PARTIAL_SUFFIX,
    backup_name,
    backups_beyond_retention,
    is_backup,
    next_backup_time,
)

LONDON = ZoneInfo("Europe/London")
BUDAPEST = ZoneInfo("Europe/Budapest")


def at(zone, *moment, fold=0):
    return datetime(*moment, tzinfo=zone, fold=fold)


@pytest.mark.parametrize(
    ("now", "due"),
    [
        (at(LONDON, 2026, 10, 17, 3, 59, 59), at(LONDON, 2026, 10, 17, 4)),
        (at(LONDON, 2026, 10, 17, 0, 0), at(LONDON, 2026, 10, 17, 4)),
        (at(LONDON, 2026, 10, 17, 4, 0), at(LONDON, 2026, 10, 18, 4)),
        (at(LONDON, 2026, 10, 17, 4, 0, 1), at(LONDON, 2026, 10, 18, 4)),
        (at(LONDON, 2026, 10, 17, 23, 30), at(LONDON, 2026, 10, 18, 4)),
    ],
)
def test_the_next_backup_is_the_next_four_oclock_in_the_deployments_zone(now, due):
    assert next_backup_time(now, LONDON) == due


def test_the_hour_is_local_to_the_zone_not_to_utc():
    due = next_backup_time(at(UTC, 2026, 10, 17, 12), BUDAPEST)

    assert due.astimezone(UTC) == at(UTC, 2026, 10, 18, 2)


def test_the_night_the_clocks_go_back_is_still_at_four_local():
    due = next_backup_time(at(LONDON, 2026, 10, 25, 0, 30), LONDON)

    assert due == at(LONDON, 2026, 10, 25, 4)
    assert due.astimezone(UTC) == at(UTC, 2026, 10, 25, 4)


def test_the_night_the_clocks_go_forward_is_still_at_four_local():
    due = next_backup_time(at(LONDON, 2026, 3, 29, 0, 30), LONDON)

    assert due.astimezone(UTC) == at(UTC, 2026, 3, 29, 3)


@pytest.mark.parametrize("restarted_at", [at(LONDON, 2026, 10, 17, 4, 0, 5), at(LONDON, 2026, 10, 17, 11)])
def test_a_restart_after_the_nights_backup_waits_for_the_next_night_rather_than_repeating_it(restarted_at):
    assert next_backup_time(restarted_at, LONDON) == at(LONDON, 2026, 10, 18, 4)


def test_a_restart_before_four_still_takes_that_nights_backup():
    assert next_backup_time(at(LONDON, 2026, 10, 17, 2), LONDON) == at(LONDON, 2026, 10, 17, 4)


def test_backup_names_sort_by_age_across_a_clock_change():
    # 01:30 BST comes before 01:10 GMT, the second time the clock reads 01:10 that night.
    moments = [at(LONDON, 2026, 10, 25, 1, 30), at(LONDON, 2026, 10, 25, 1, 10, fold=1)]

    names = [backup_name(moment) for moment in moments]

    assert sorted(names) == names
    assert all(is_backup(name) for name in names)


def test_retention_deletes_all_but_the_seven_newest():
    first = at(UTC, 2026, 10, 1, 4)
    names = [backup_name(first + timedelta(days=day)) for day in range(10)]

    deleted = backups_beyond_retention(reversed(names))

    assert deleted == names[: 10 - KEPT_BACKUPS]


def test_retention_deletes_nothing_while_seven_or_fewer_exist():
    first = at(UTC, 2026, 10, 1, 4)

    assert backups_beyond_retention(backup_name(first + timedelta(days=day)) for day in range(7)) == []


def test_a_half_written_backup_or_any_other_file_is_never_counted_or_deleted():
    first = at(UTC, 2026, 10, 1, 4)
    names = [backup_name(first + timedelta(days=day)) for day in range(7)]
    others = [backup_name(first - timedelta(days=1)) + PARTIAL_SUFFIX, "db.sqlite3", "restore-me.sqlite3"]

    assert backups_beyond_retention(names + others) == []
    assert not any(is_backup(name) for name in others)
