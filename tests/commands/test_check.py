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


def test_the_deployment_checklist_passes_with_production_values():
    environ = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "ribcage.settings",
        "DEBUG": "false",
        "SECRET_KEY": "Production-length key of fifty characters or more, Z9#q",
        "ALLOWED_HOSTS": "ribcage.example.org",
        "CSRF_TRUSTED_ORIGINS": "https://ribcage.example.org",
    }

    check = subprocess.run(
        [sys.executable, "-m", "django", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=REPO_ROOT,
        env=environ,
        capture_output=True,
        text=True,
    )

    assert check.returncode == 0, check.stderr
    assert "System check identified no issues" in check.stdout
