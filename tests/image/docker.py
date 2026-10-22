import subprocess
from pathlib import Path

import ribcage

REPO_ROOT = Path(ribcage.__file__).parents[1]
# BuildKit copies the filtered context out to a directory, so listing it needs no base image.
CONTEXT_COPY = "FROM scratch\nCOPY . /\n"


# UTF-8, since Windows would decode docker's output as cp1252.
def run_docker(*arguments, input=None, timeout=600, env=None):
    return subprocess.run(["docker", *arguments], input=input, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)


def docker(*arguments, input=None, timeout=600, env=None):
    result = run_docker(*arguments, input=input, timeout=timeout, env=env)
    assert result.returncode == 0, f"docker {' '.join(arguments)} failed:\n{result.stderr}"
    return result.stdout


def build_context_of(directory, destination):
    docker("build", "--file", "-", "--output", f"type=local,dest={destination}", str(directory), input=CONTEXT_COPY)
    return {path.relative_to(destination).as_posix() for path in destination.rglob("*")}
