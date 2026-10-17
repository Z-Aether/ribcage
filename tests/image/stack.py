import json
import os
import re
import uuid

from tests.image.conftest import IMAGE
from tests.image.docker import REPO_ROOT, docker, run_docker

EXAMPLE_FILE = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
EXAMPLE = dict(re.findall(r"^([A-Z][A-Z_]+)=(.*)$", EXAMPLE_FILE, re.MULTILINE))
NAMED = set(re.findall(r"^#? ?([A-Z][A-Z_]+)=", EXAMPLE_FILE, re.MULTILINE))
# The stack runs the image under test, never a pinned or local build, on an ephemeral loopback port,
# since the host's 8080 or 8000 may be taken; compose config pins the base file's own port.
ON_THE_IMAGE_UNDER_TEST = (
    f"services:\n  ribcage:\n    image: {IMAGE}\n    ports: !override\n      - 127.0.0.1::8000\n"
    f"  backup:\n    image: {IMAGE}\n"
)
LOCALLY_ON_THE_IMAGE_UNDER_TEST = (
    f"services:\n  ribcage:\n    image: {IMAGE}\n    build: !reset null\n    ports: !override\n      - 127.0.0.1::8000\n"
    f"  backup:\n    image: {IMAGE}\n"
)


def without_the_settings():
    # Compose prefers the caller's environment to --env-file, and tests.settings fills it from .env.example.
    return {name: value for name, value in os.environ.items() if name not in NAMED}


class Stack:
    def __init__(self, directory, files, environment):
        self.project = f"ribcage-pytest-{uuid.uuid4().hex[:8]}"
        env_file = directory / f"{self.project}.env"
        env_file.write_text("".join(f"{name}={value}\n" for name, value in environment.items()))
        self.arguments = ["compose", "--project-name", self.project, "--project-directory", str(REPO_ROOT)]
        self.arguments += ["--env-file", str(env_file)]
        for file in files:
            self.arguments += ["--file", str(file)]

    def run(self, *arguments, timeout=300):
        return run_docker(*self.arguments, *arguments, timeout=timeout, env=without_the_settings())

    def __call__(self, *arguments):
        return docker(*self.arguments, *arguments, env=without_the_settings())

    def container(self, service="ribcage"):
        return self("ps", "--quiet", service).strip()

    def inspect(self, template, service="ribcage"):
        return json.loads(docker("inspect", self.container(service), "--format", f"{{{{json {template}}}}}"))

    def port(self):
        return int(self("port", "ribcage", "8000").strip().rsplit(":", 1)[1])

    def journal_mode(self):
        query = "import sqlite3; print(sqlite3.connect('/data/db.sqlite3').execute('PRAGMA journal_mode').fetchone()[0])"
        return self("exec", "ribcage", "python", "-c", query).strip()


def override(directory, name, text):
    path = directory / name
    path.write_text(text)
    return path
