import subprocess
from pathlib import Path

import ribcage

REPO_ROOT = Path(ribcage.__file__).parents[1]
# BuildKit copies the filtered context out to a directory, so listing it needs no base image.
CONTEXT_COPY = "FROM scratch\nCOPY . /\n"


def run_docker(*arguments, input=None, timeout=600):
    return subprocess.run(["docker", *arguments], input=input, capture_output=True, text=True, timeout=timeout)


def docker(*arguments, input=None, timeout=600):
    result = run_docker(*arguments, input=input, timeout=timeout)
    assert result.returncode == 0, f"docker {' '.join(arguments)} failed:\n{result.stderr}"
    return result.stdout


def build_context_of(directory, destination):
    docker("build", "--file", "-", "--output", f"type=local,dest={destination}", str(directory), input=CONTEXT_COPY)
    return {path.relative_to(destination).as_posix() for path in destination.rglob("*")}
