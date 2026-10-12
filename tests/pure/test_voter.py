from django.contrib.auth import get_user_model

from ribcage.identity.models import Voter


def test_voter_is_the_user_model():
    assert get_user_model() is Voter


def test_voter_cannot_represent_staff_or_superuser():
    field_names = {field.name for field in Voter._meta.get_fields()}

    assert not field_names & {"is_staff", "is_superuser", "groups", "user_permissions"}
