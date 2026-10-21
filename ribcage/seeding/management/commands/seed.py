from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from ribcage.hello.models import Message
from ribcage.identity.models import Voter

SEEDED_DISPLAY_NAMES = ["Ada", "Anne-Marie", "O'Brien", "Zoë", "Sam", "Bartholomew Winthrop"]
SEEDED_PASSWORD = "popcorn-before-midnight"
# A fresh database starts in SUGGEST; M3 adds the five phases, and each milestone seeds what it builds (#25).
FRESH_PHASE = "SUGGEST"
SEEDED_MESSAGES = ["Seeded for the local instance", "Who is bringing the projector?", "Popcorn at seven"]


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
        if options["phase"] != FRESH_PHASE:
            raise CommandError(
                f"Phases arrive in M3. Until then only {FRESH_PHASE}, the fresh phase, can be seeded, "
                f"not {options['phase']!r}."
            )
        rebuild_from_nothing()
        with transaction.atomic():
            password = make_password(SEEDED_PASSWORD)
            for display_name in SEEDED_DISPLAY_NAMES:
                Voter.objects.create_voter(display_name, password_hash=password)
            # One create each, never bulk_create, so Message's own trimming runs (#47).
            for text in SEEDED_MESSAGES:
                Message.objects.create(text=text)
        # Redirected on Windows, stdout would be cp1252 and mangle Zoë in a log read as UTF-8 (#50).
        # This reconfigures the whole process's stdout, not just this command's.
        if hasattr(self.stdout, "reconfigure"):
            self.stdout.reconfigure(encoding="utf-8")
        self.stdout.write(f"Seeded {FRESH_PHASE} with {len(SEEDED_MESSAGES)} hello messages and these voters:")
        self.stdout.write(f"  {', '.join(SEEDED_DISPLAY_NAMES)}")
        self.stdout.write(f"  each signing in with the password {SEEDED_PASSWORD}")


def add_phase_argument(parser):
    parser.add_argument("--phase", default=FRESH_PHASE, help="The phase to seed the marathon into.")


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
