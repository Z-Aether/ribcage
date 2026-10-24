"""The Films tab's ledger as plain data: the filter `?show=` names, its rows and counts, and the ballot's screen time (#28, #95)."""

from dataclasses import replace

import pytest

from ribcage.console.films import ALL, FILTERS, Ledger, Row, chosen, may_approve, screen_time_words
from ribcage.films import card
from ribcage.suggestions.models import Approval
from tests.films import THE_SHINING

UNDECIDED, APPROVED, DROPPED = Approval.UNDECIDED, Approval.APPROVED, Approval.DROPPED


def a_row(approval, runtime=100, pitch="A pitch.", notes=()):
    film_card = card.FilmCard(film=replace(THE_SHINING, runtime=runtime), suggester="Ada", suggester_removed=False, pitch=pitch, notes=notes)
    return Row(film_card, approval)


@pytest.mark.parametrize("show, label", [("undecided", "Undecided"), ("approved", "On the ballot"), ("dropped", "Dropped"), ("all", "All")])
def test_show_names_its_filter(show, label):
    assert chosen(show).label == label


@pytest.mark.parametrize("show", [None, "", "Approved", "ballot", "removed"])
def test_a_show_that_names_no_filter_is_all(show):
    assert chosen(show) is ALL


def test_each_filter_reloads_onto_its_own_address():
    assert [each.address for each in FILTERS] == [
        "/console/films/",
        "/console/films/?show=undecided",
        "/console/films/?show=approved",
        "/console/films/?show=dropped",
    ]


def test_the_note_count_includes_the_pitch():
    notes = (card.Note("Bo", "In."), card.Note("Cy", "Me too."))

    assert a_row(UNDECIDED, notes=notes).note_count == 3
    assert a_row(UNDECIDED, pitch=None, notes=notes).note_count == 2


def test_a_filter_keeps_its_rows_in_order_and_every_count_stays_whole():
    rows = [a_row(APPROVED, 90), a_row(UNDECIDED, 80), a_row(APPROVED, 130), a_row(DROPPED, 70)]

    ledger = Ledger.of(rows, chosen("approved"))

    assert ledger.rows == (rows[0], rows[2])
    assert [(tally.show.label, tally.count, tally.is_chosen) for tally in ledger.filters] == [
        ("All", 4, False),
        ("Undecided", 1, False),
        ("On the ballot", 2, True),
        ("Dropped", 1, False),
    ]
    assert (ledger.ballot_size, ledger.screen_time) == (2, 220)


@pytest.mark.parametrize("minutes, words", [(0, "0 min"), (47, "47 min"), (60, "1 h"), (352, "5 h 52 min"), (1505, "25 h 5 min")])
def test_screen_time_in_hours_and_minutes(minutes, words):
    assert screen_time_words(minutes) == words


@pytest.mark.parametrize("runtime, approvable", [(None, False), (1, True), (144, True)])
def test_only_a_film_with_a_runtime_may_be_approved(runtime, approvable):
    assert may_approve(runtime) is approvable


@pytest.mark.parametrize("approval, runtime, acts", [
    (UNDECIDED, 100, (True, True)),
    (APPROVED, 100, (False, True)),
    (DROPPED, 100, (True, False)),
    (UNDECIDED, None, (False, True)),
    (DROPPED, None, (False, False)),
])
def test_a_row_offers_the_acts_that_would_change_its_approval(approval, runtime, acts):
    row = a_row(approval, runtime)

    assert (row.may_approve, row.may_drop) == acts


def a_timed_row(runtime, tmdb_runtime, approval=UNDECIDED):
    return replace(a_row(approval, runtime), tmdb_runtime=tmdb_runtime)


@pytest.mark.parametrize(("runtime", "tmdb_runtime", "says"), [
    (144, 144, None),
    (146, 144, 144),
    (120, 144, 144),
    # A cleared runtime differs from TMDB's too (#97).
    (None, 144, 144),
    # A hand-entered film, or one TMDB gave no runtime, has nothing to differ from.
    (47, None, None),
    (None, None, None),
])
def test_tmdb_says_its_runtime_only_while_the_runtime_differs_from_it(runtime, tmdb_runtime, says):
    assert a_timed_row(runtime, tmdb_runtime).tmdb_says == says


@pytest.mark.parametrize(("runtime", "required"), [(None, True), (1, False), (144, False)])
def test_a_runtime_is_required_exactly_when_approve_is_unavailable_for_want_of_one(runtime, required):
    row = a_row(UNDECIDED, runtime)

    assert row.runtime_required is required
    assert row.may_approve is (not required)
