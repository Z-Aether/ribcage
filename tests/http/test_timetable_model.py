"""The timetable and its boxes: what the database refuses, and the hold a box puts on its film (#12, #26 §8, #135)."""

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from ribcage.suggestions.models import Suggestion
from ribcage.suggestions.withdrawal import with_holds, withdrawable
from ribcage.timetable import setting
from ribcage.timetable.models import Box, Timetable
from tests.films import a_tmdb_film


@pytest.fixture
def cube(voters):
    return Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(431, "Cube", runtime=90), "Six strangers.")


def refused(**fields):
    with pytest.raises(IntegrityError), transaction.atomic():
        Box.objects.create(**fields)


def test_a_film_box_and_a_labelled_box_are_stored(cube):
    Box.objects.create(suggestion=cube, start=-30)
    Box.objects.create(label="Break", length=30, start=90)
    Box.objects.create(label="Dinner", length=5, flexible=True, start=0)

    assert Box.objects.count() == 3


def test_a_second_box_for_one_film_is_refused(cube):
    Box.objects.create(suggestion=cube, start=0)

    refused(suggestion=cube, start=200)


@pytest.mark.parametrize(
    "fields",
    [{"label": "Break"}, {"length": 30}, {"flexible": True}, {"label": "Break", "length": 30}],
    ids=["a label", "a length", "flexible", "a label and a length"],
)
def test_a_film_box_has_no_label_length_or_flexible(cube, fields):
    refused(suggestion=cube, start=0, **fields)


@pytest.mark.parametrize(
    "fields",
    [{"label": "", "length": 30}, {"label": "Break"}, {"label": "Break", "length": 4}, {"length": 30}],
    ids=["no label", "no length", "a length under 5", "an empty label"],
)
def test_a_labelled_box_has_a_label_and_a_length_of_at_least_five(db, fields):
    refused(start=0, **fields)


def test_only_a_labelled_box_may_be_flexible(cube):
    refused(suggestion=cube, start=0, flexible=True)
    Box.objects.create(label="Break", length=30, flexible=True, start=0)


def test_deleting_a_boxed_suggestion_raises_protected_error(cube):
    Box.objects.create(suggestion=cube, start=0)

    with pytest.raises(ProtectedError):
        cube.delete()


def test_a_box_holds_its_film_in_with_holds(cube):
    free = Suggestion.objects.suggest(cube.suggester, a_tmdb_film(432, "Saw", runtime=100), "Pitch.")
    Box.objects.create(suggestion=cube, start=0)

    held = {each.pk: withdrawable(each) for each in with_holds(Suggestion.objects.all())}

    assert held == {cube.pk: False, free.pk: True}


def test_no_row_means_an_empty_timetable_and_a_second_row_is_refused(db):
    assert (setting.read().anchor, setting.read().budget) == (None, None)
    assert not Timetable.objects.exists()
    with pytest.raises(IntegrityError), transaction.atomic():
        Timetable.objects.create(pk=2)


def test_a_zero_budget_is_refused(db):
    with pytest.raises(IntegrityError), transaction.atomic():
        Timetable.objects.create(pk=1, budget=0)
