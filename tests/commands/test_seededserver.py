import pytest
from django.core.management import CommandError, call_command

from ribcage.identity.models import Voter


def test_with_debug_off_it_refuses_before_seeding_or_serving(transactional_db, settings):
    settings.DEBUG = False
    Voter.objects.create_voter("Before the seed")

    with pytest.raises(CommandError, match="only with DEBUG on"):
        call_command("seededserver")

    assert list(Voter.objects.values_list("display_name", flat=True)) == ["Before the seed"]


def test_it_passes_the_phase_on_to_seed(transactional_db, debug_on):
    with pytest.raises(CommandError, match="Phases arrive in M3"):
        call_command("seededserver", "--phase", "VOTE")
