import pytest
from django.core.management import CommandError, call_command

from ribcage.hello.models import Message

# The pages these tests fetch render static tags, which need collectstatic's output with DEBUG off (#46).
pytestmark = pytest.mark.usefixtures("collected_static_files")


def test_with_debug_off_it_refuses_before_seeding_or_serving(transactional_db, settings, client):
    settings.DEBUG = False
    Message.objects.create(text="Written before the seed")

    with pytest.raises(CommandError, match="only with DEBUG on"):
        call_command("seededserver")

    assert "Written before the seed" in client.get("/").text


def test_it_passes_the_phase_on_to_seed(transactional_db, debug_on):
    with pytest.raises(CommandError, match="Phases arrive in M3"):
        call_command("seededserver", "--phase", "VOTE")
