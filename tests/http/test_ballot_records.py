"""The ballot's records: what the database holds them to, and that a record holds its film (#26 §8, #34, #118)."""

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from ribcage.ballot.models import BallotRecord, DoneMarker
from ribcage.suggestions.models import Suggestion
from tests.films import a_tmdb_film


@pytest.fixture
def thing(voters):
    return Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing"), "Lights off.")


def refused(**fields):
    with pytest.raises(IntegrityError), transaction.atomic():
        BallotRecord.objects.create(**fields)


@pytest.mark.parametrize("score", [-1, 0, 1, 2, 3])
def test_every_step_of_the_scale_is_kept(voters, thing, score):
    BallotRecord.objects.create(voter=voters["ada"], suggestion=thing, score=score)

    assert BallotRecord.objects.get().score == score


@pytest.mark.parametrize("score", [-2, 4])
def test_a_score_outside_the_scale_is_refused(voters, thing, score):
    refused(voter=voters["ada"], suggestion=thing, score=score)


def test_a_vetoed_record_with_a_score_is_refused(voters, thing):
    refused(voter=voters["ada"], suggestion=thing, vetoed=True, score=0)


def test_a_reason_on_a_record_that_is_not_vetoed_is_refused(voters, thing):
    refused(voter=voters["ada"], suggestion=thing, score=1, veto_reason="Too loud.")
    refused(voter=voters["Dani"], suggestion=thing, seen_it=True, veto_reason="")


def test_a_veto_keeps_its_reason_or_none_and_may_sit_beside_seen_it(voters, thing):
    BallotRecord.objects.create(voter=voters["ada"], suggestion=thing, vetoed=True, veto_reason="Too loud.", seen_it=True)
    BallotRecord.objects.create(voter=voters["Dani"], suggestion=thing, vetoed=True)

    assert BallotRecord.objects.filter(vetoed=True, seen_it=True).count() == 1
    assert BallotRecord.objects.filter(vetoed=True, veto_reason__isnull=True).count() == 1


def test_a_second_record_for_one_voter_and_suggestion_is_refused(voters, thing):
    BallotRecord.objects.create(voter=voters["ada"], suggestion=thing, score=1)

    refused(voter=voters["ada"], suggestion=thing, score=2)


def test_a_second_done_marker_for_one_voter_is_refused(voters):
    DoneMarker.objects.create(voter=voters["ada"])

    with pytest.raises(IntegrityError), transaction.atomic():
        DoneMarker.objects.create(voter=voters["ada"])


def test_deleting_a_suggestion_that_has_a_record_raises(voters, thing):
    BallotRecord.objects.create(voter=voters["ada"], suggestion=thing, seen_it=True)

    with pytest.raises(ProtectedError):
        thing.delete()
    assert Suggestion.objects.filter(pk=thing.pk).exists()
