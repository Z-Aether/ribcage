import os
import subprocess
import sys
from pathlib import Path

import ribcage

REPO_ROOT = Path(ribcage.__file__).parents[1]


def test_the_process_exits_naming_the_missing_variable():
    environ = {**os.environ, "DJANGO_SETTINGS_MODULE": "ribcage.settings"}
    del environ["JOIN_CODE"]

    startup = subprocess.run(
        [sys.executable, "-m", "django", "check"],
        cwd=REPO_ROOT,
        env=environ,
        capture_output=True,
        text=True,
    )

    assert startup.returncode != 0
    assert "Set the JOIN_CODE environment variable." in startup.stderr
