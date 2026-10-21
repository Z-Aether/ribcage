import pytest
from django.core.management import CommandError, call_command

from ribcage.identity.models import Voter
from ribcage.phase.history import current
from ribcage.phase.order import Phase
from ribcage.seeding.management.commands import seededserver


def test_with_debug_off_it_refuses_before_seeding_or_serving(transactional_db, settings):
    settings.DEBUG = False
    Voter.objects.create_voter("Before the seed")

    with pytest.raises(CommandError, match="only with DEBUG on"):
        call_command("seededserver")

    assert list(Voter.objects.values_list("display_name", flat=True)) == ["Before the seed"]


def test_it_refuses_a_phase_seed_would_refuse_before_seeding_or_serving(transactional_db, debug_on):
    Voter.objects.create_voter("Before the seed")

    with pytest.raises(CommandError, match="invalid choice"):
        call_command("seededserver", "--phase", "SETUP")

    assert list(Voter.objects.values_list("display_name", flat=True)) == ["Before the seed"]


def test_it_passes_the_phase_on_to_seed_then_serves(transactional_db, debug_on, monkeypatch):
    served = []
    real_call_command = seededserver.call_command

    def serve_nothing(name, *args, **options):
        if name == "runserver":
            served.append(name)
        else:
            real_call_command(name, *args, **options)

    monkeypatch.setattr(seededserver, "call_command", serve_nothing)

    call_command("seededserver", "--phase", "VOTE")

    assert current() is Phase.VOTE
    assert served == ["runserver"]
