import os
import subprocess
import sys
from pathlib import Path

import ribcage

REPO_ROOT = Path(ribcage.__file__).parents[1]
# Two admin tabs move from SUGGEST at once, each lingering after it reads the phase.
TWO_MOVES_AT_ONCE = """
import threading, time
import django
django.setup()
from django.core.management import call_command
from django.db import connection
from ribcage.phase import history
from ribcage.phase.order import MoveRefused

call_command("migrate", verbosity=0)
read = history.current

def lingering_read():
    phase = read()
    time.sleep(0.5)
    return phase

history.current = lingering_read
outcomes = []

def mover():
    try:
        history.move("SUGGEST", "APPROVE")
        outcomes.append("moved")
    except MoveRefused:
        outcomes.append("refused")
    finally:
        connection.close()

movers = [threading.Thread(target=mover) for _ in range(2)]
for each in movers:
    each.start()
for each in movers:
    each.join()
print(sorted(outcomes), list(history.PhaseMove.objects.values_list("phase", flat=True)))
"""


def test_two_moves_from_the_same_phase_at_once_append_one_entry_and_refuse_the_other(tmp_path):
    environ = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "ribcage.settings",
        "DATABASE_PATH": str(tmp_path / "race.sqlite3"),
    }

    race = subprocess.run(
        [sys.executable, "-c", TWO_MOVES_AT_ONCE], cwd=REPO_ROOT, env=environ, capture_output=True, text=True
    )

    assert race.returncode == 0, race.stderr
    assert race.stdout.strip() == "['moved', 'refused'] ['APPROVE']"
