from django.core.management import call_command
from django.core.management.base import BaseCommand

from ribcage.films import client
from ribcage.seeding.management.commands.seed import add_phase_argument
from ribcage.seeding.recorded import RecordedDtdd, RecordedTmdb
from ribcage.triggers import client as dtdd_client

# Fixed so guides and Playwright can name the address; local only, as the Secure cookies need (#31, #50).
SEEDED_INSTANCE_ADDRESS = "127.0.0.1:8000"


class Command(BaseCommand):
    help = f"Seed the local database, then serve it at http://{SEEDED_INSTANCE_ADDRESS}/, answering TMDB and DoesTheDogDie from the recordings."

    def add_arguments(self, parser):
        add_phase_argument(parser)

    def handle(self, *args, **options):
        call_command("seed", phase=options["phase"])
        # Flushed so a background run's log shows the seeded voters before the server blocks.
        self.stdout.flush()
        # Browser checks reach TMDB only through the recordings; seed has already refused without DEBUG (#50, #92).
        client.answer_from(RecordedTmdb())
        # And DoesTheDogDie, so suggesting a recorded film stores its snapshot; anything unrecorded isn't answering (#102).
        dtdd_client.answer_from(RecordedDtdd())
        # No autoreload: its restarts would rerun this command, so a code change means a restart and a fresh seed.
        # call_command skips system checks unless told otherwise; the shell's runserver runs them (#50).
        call_command("runserver", SEEDED_INSTANCE_ADDRESS, use_reloader=False, skip_checks=False)
