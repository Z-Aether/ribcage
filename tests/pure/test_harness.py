import pytest

from ribcage.identity.models import Voter


def test_database_access_fails_the_test():
    with pytest.raises(RuntimeError, match="Database access not allowed"):
        Voter.objects.exists()
