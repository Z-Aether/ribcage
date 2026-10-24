"""A phase move's DoesTheDogDie refresh holds no write lock while it waits on DoesTheDogDie, so other writers go ahead (#74, #104)."""

import os
import subprocess
import sys
from pathlib import Path

import ribcage

REPO_ROOT = Path(ribcage.__file__).parents[1]
# A move, as the Phase tab makes it, then a voter registering during each of the refresh's calls to DoesTheDogDie.
A_WRITER_DURING_THE_REFRESH = """
import threading, time
import django
django.setup()
from django.core.management import call_command
from django.db import connection
from ribcage.identity.models import Voter
from ribcage.phase import history
from ribcage.suggestions.models import Suggestion
from ribcage.triggers import client, refresh
from tests.dtdd import Dtdd, detail, item
from tests.films import a_tmdb_film

call_command("migrate", verbosity=0)
weapons = item(14, "Weapons", 2025)
Suggestion.objects.suggest(Voter.objects.create_voter("Ada"), a_tmdb_film(1078605, "Weapons"), "Pitch.")
waits = []

def register(name):
    try:
        Voter.objects.create_voter(name)
    finally:
        connection.close()

def a_writer_meanwhile(path):
    started = time.monotonic()
    writer = threading.Thread(target=register, args=(f"Voter {len(waits)}",))
    writer.start()
    # SQLite's busy timeout is 20 s, so a writer held up by the lock is still waiting when this gives up.
    writer.join(timeout=5)
    waits.append("held up" if writer.is_alive() else "went ahead")

client.over_the_network = Dtdd(by_tmdb={1078605: [weapons]}, details=[detail(weapons, (200, 4, 0))], on_call=a_writer_meanwhile)
history.move("SUGGEST", "APPROVE")
refresh.after_the_move()
print(waits, Voter.objects.count())
"""


def test_another_writer_is_not_held_up_while_the_refresh_waits_on_dtdd(tmp_path):
    environ = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "ribcage.settings",
        "DATABASE_PATH": str(tmp_path / "refresh.sqlite3"),
    }

    run = subprocess.run(
        [sys.executable, "-c", A_WRITER_DURING_THE_REFRESH], cwd=REPO_ROOT, env=environ, capture_output=True, text=True, timeout=120
    )

    assert run.returncode == 0, run.stderr
    # The vocabulary's three calls, then Weapons' lookup and its detail.
    assert run.stdout.strip() == f"{['went ahead'] * 5} 6"
