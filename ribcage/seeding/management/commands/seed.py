from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from ribcage.identity.models import Voter
from ribcage.phase.models import PhaseMove
from ribcage.phase.order import FRESH_PHASE, PHASES, Phase
from ribcage.films.corpus import FETCH_COMMAND
from ribcage.seeding.ballots import seed_the_ballots
from ribcage.seeding.timetable import seed_the_timetable
from ribcage.seeding.watched import seed_the_watched_lists
from ribcage.seeding.pool import SEEDED_POOL, seed_the_pool, seed_the_trigger_data, trigger_states
from ribcage.triggers import stored
from ribcage.triggers.status import State

SEEDED_DISPLAY_NAMES = ["Ada", "Anne-Marie", "O'Brien", "Zoë", "Sam", "Bartholomew Winthrop"]
SEEDED_PASSWORD = "popcorn-before-midnight"
# How long before the seed each phase was entered: a few weeks' window, the evening on the day (#74).
ENTERED_AGO = {
    Phase.APPROVE: timedelta(days=12),
    Phase.VOTE: timedelta(days=9),
    Phase.PICK: timedelta(days=2),
    Phase.RUN: timedelta(hours=3),
}


class Command(BaseCommand):
    help = "Rebuild the local database from nothing and fill it with known development data."

    def add_arguments(self, parser):
        add_phase_argument(parser)

    def handle(self, *args, **options):
        # The deployment runs with DEBUG off, so this guard is all that keeps seed from wiping it (#50).
        if not settings.DEBUG:
            raise CommandError(
                "seed rebuilds the database from nothing, so it runs only with DEBUG on. Set DEBUG=true in .env."
            )
        phase = Phase(options["phase"])
        rebuild_from_nothing()
        with transaction.atomic():
            password = make_password(SEEDED_PASSWORD)
            for display_name in SEEDED_DISPLAY_NAMES:
                Voter.objects.create_voter(display_name, password_hash=password)
            walk_the_phase_to(phase)
            seed_the_pool(phase)
            recordings = seed_the_trigger_data()
            seed_the_watched_lists(recordings)
            # From VOTE on, as PICK and RUN keep the scores for M8's reveal (#119).
            if phase in (Phase.VOTE, Phase.PICK, Phase.RUN):
                seed_the_ballots()
            if phase in (Phase.PICK, Phase.RUN):
                seed_the_timetable()
            if phase is Phase.RUN:
                # As entering RUN leaves it: the matches and setters, no snapshot, no vocabulary (#106).
                stored.purge()
        # Redirected on Windows, stdout would be cp1252 and mangle Zoë in a log read as UTF-8 (#50).
        # This reconfigures the whole process's stdout, not just this command's.
        if hasattr(self.stdout, "reconfigure"):
            self.stdout.reconfigure(encoding="utf-8")
        self.stdout.write(f"Seeded {phase} with these voters:")
        self.stdout.write(f"  {', '.join(SEEDED_DISPLAY_NAMES)}")
        self.stdout.write(f"  each signing in with the password {SEEDED_PASSWORD}")
        self.stdout.write(f"and {len(SEEDED_POOL)} films in the pool.")
        if phase is Phase.RUN:
            self.stdout.write("DoesTheDogDie: no snapshots or vocabulary, as entering RUN leaves them.")
            return
        states = trigger_states()
        self.stdout.write("DoesTheDogDie: " + ", ".join(f"{states[state]} {state}" for state in State) + ".")
        if not recordings.is_recorded:
            # Gitignored under DTDD's terms, so a fresh clone lands here (#40).
            self.stdout.write(
                "DoesTheDogDie's recordings are missing, so every film is left not fetched and the vocabulary empty. "
                f"Run {FETCH_COMMAND} with the keys set to record them."
            )


def add_phase_argument(parser):
    parser.add_argument("--phase", default=FRESH_PHASE, choices=PHASES, help="The phase to seed the marathon into.")


def walk_the_phase_to(phase):
    # History written directly, not through move: its later effects, like the DTDD refresh, go online (#57, #74).
    now = timezone.now()
    PhaseMove.objects.bulk_create(
        PhaseMove(phase=step, at=now - ENTERED_AGO[step]) for step in PHASES[1 : PHASES.index(phase) + 1]
    )


def rebuild_from_nothing():
    # Dropping tables rather than deleting the file works while a server holds the database open (#50).
    connection.disable_constraint_checking()
    try:
        with connection.cursor() as cursor:
            for table in connection.introspection.table_names(cursor):
                cursor.execute(f"DROP TABLE {connection.ops.quote_name(table)}")
    finally:
        connection.enable_constraint_checking()
    call_command("migrate", interactive=False, verbosity=0)
