import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from ribcage.identity.models import Voter
from tests.http.signing_in import PASSWORD


def test_creating_a_voter_normalises_and_keeps_the_case_as_typed(db):
    voter = Voter.objects.create_voter("  sAM   Q ", PASSWORD)

    assert Voter.objects.get().display_name == "sAM Q"
    assert voter.check_password(PASSWORD)


def test_creating_a_voter_validates(db):
    with pytest.raises(ValidationError):
        Voter.objects.create_voter("Sa\u200bm")
    assert not Voter.objects.exists()


def test_the_manager_refuses_a_name_taken_in_another_case(db):
    Voter.objects.create_voter("sam")

    with pytest.raises(ValidationError):
        Voter.objects.create_voter("Sam")


def test_a_name_taken_by_a_registration_racing_this_one_is_refused_as_taken(db, monkeypatch):
    Voter.objects.create_voter("sam")
    # As if the racing registration saved after any check this one makes (#69).
    monkeypatch.setattr(QuerySet, "exists", lambda queryset: False)

    with pytest.raises(ValidationError) as refused:
        Voter.objects.create_voter("Sam")

    assert refused.value.code == "taken"
    assert Voter.objects.count() == 1


def test_the_database_refuses_a_name_taken_in_another_case(db):
    Voter.objects.create_voter("sam")

    with pytest.raises(IntegrityError), transaction.atomic():
        Voter.objects.create(display_name="Sam")


@pytest.mark.parametrize("typed", ["Sam", "SAM", "sam", " sAm "])
def test_signing_in_ignores_case(db, typed):
    voter = Voter.objects.create_voter("Sam", PASSWORD)

    assert authenticate(display_name=typed, password=PASSWORD) == voter


def test_signing_in_refuses_a_wrong_password_and_an_unknown_name(db):
    Voter.objects.create_voter("Sam", PASSWORD)

    assert authenticate(display_name="SAM", password="wrong") is None
    assert authenticate(display_name="Nobody", password=PASSWORD) is None


def test_the_manager_and_the_database_refuse_a_name_taken_in_another_case_beyond_ascii(db):
    Voter.objects.create_voter("éva")

    with pytest.raises(ValidationError):
        Voter.objects.create_voter("Éva")
    with pytest.raises(IntegrityError), transaction.atomic():
        Voter.objects.create(display_name="Éva")


def test_signing_in_ignores_case_beyond_ascii(db):
    voter = Voter.objects.create_voter("éva", PASSWORD)

    assert authenticate(display_name="ÉVA", password=PASSWORD) == voter


def test_signing_in_answers_to_username_as_django_forms_send_it(db):
    voter = Voter.objects.create_voter("Sam", PASSWORD)
    form = AuthenticationForm(data={"username": "SAM", "password": PASSWORD})

    assert form.is_valid()
    assert form.get_user() == voter
