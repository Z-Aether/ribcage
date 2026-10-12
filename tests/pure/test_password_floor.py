import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from ribcage.identity.models import Voter


@pytest.mark.parametrize(
    ("password", "refusal"),
    [
        ("Marigold77", "too similar to the display name"),
        ("x7Qp!a", "too short"),
        ("password123", "too common"),
        ("4815162342", "entirely numeric"),
    ],
)
def test_the_four_default_checks_refuse_a_weak_password(password, refusal):
    with pytest.raises(ValidationError, match=refusal):
        validate_password(password, Voter(display_name="Marigold"))


def test_a_password_passing_every_check_is_accepted():
    validate_password("velvet-lantern-orbit", Voter(display_name="Marigold"))
