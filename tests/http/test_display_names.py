import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from ribcage.identity.models import Voter


@pytest.fixture(autouse=True)
def fast_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


def test_creating_a_voter_normalises_and_keeps_the_case_as_typed(db):
    voter = Voter.objects.create_voter("  sAM   Q ", "popcorn-before-midnight")

    assert Voter.objects.get().display_name == "sAM Q"
    assert voter.check_password("popcorn-before-midnight")


def test_creating_a_voter_validates(db):
    with pytest.raises(ValidationError):
        Voter.objects.create_voter("Sa\u200bm")
    assert not Voter.objects.exists()


def test_the_manager_refuses_a_name_taken_in_another_case(db):
    Voter.objects.create_voter("sam")

    with pytest.raises(ValidationError):
        Voter.objects.create_voter("Sam")


def test_the_database_refuses_a_name_taken_in_another_case(db):
    Voter.objects.create_voter("sam")

    with pytest.raises(IntegrityError), transaction.atomic():
        Voter.objects.create(display_name="Sam")


@pytest.mark.parametrize("typed", ["Sam", "SAM", "sam", " sAm "])
def test_signing_in_ignores_case(db, typed):
    voter = Voter.objects.create_voter("Sam", "popcorn-before-midnight")

    assert authenticate(display_name=typed, password="popcorn-before-midnight") == voter


def test_signing_in_refuses_a_wrong_password_and_an_unknown_name(db):
    Voter.objects.create_voter("Sam", "popcorn-before-midnight")

    assert authenticate(display_name="SAM", password="wrong") is None
    assert authenticate(display_name="Nobody", password="popcorn-before-midnight") is None


def test_the_manager_and_the_database_refuse_a_name_taken_in_another_case_beyond_ascii(db):
    Voter.objects.create_voter("éva")

    with pytest.raises(ValidationError):
        Voter.objects.create_voter("Éva")
    with pytest.raises(IntegrityError), transaction.atomic():
        Voter.objects.create(display_name="Éva")


def test_signing_in_ignores_case_beyond_ascii(db):
    voter = Voter.objects.create_voter("éva", "popcorn-before-midnight")

    assert authenticate(display_name="ÉVA", password="popcorn-before-midnight") == voter


def test_signing_in_answers_to_username_as_django_forms_send_it(db):
    voter = Voter.objects.create_voter("Sam", "popcorn-before-midnight")
    form = AuthenticationForm(data={"username": "SAM", "password": "popcorn-before-midnight"})

    assert form.is_valid()
    assert form.get_user() == voter
