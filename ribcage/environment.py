import os

from django.core.exceptions import ImproperlyConfigured


def required(name):
    value = os.environ.get(name, "")
    # An empty value counts as missing, so the compose file's empty placeholders stop startup (#18).
    if not value.strip():
        raise ImproperlyConfigured(f"Set the {name} environment variable.")
    return value.strip()


def required_list(name):
    return [item.strip() for item in required(name).split(",") if item.strip()]


def flag(name, default):
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    if value not in ("true", "false"):
        raise ImproperlyConfigured(f"Set {name} to true or false, not {value!r}.")
    return value == "true"


def positive_whole_number(name, default):
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    # No judgement constant has a sensible zero, so zero is refused.
    if not value.isdecimal() or int(value) < 1:
        raise ImproperlyConfigured(f"Set {name} to a whole number of at least 1, not {value!r}.")
    return int(value)


def load_file(path):
    # Docker's env-file format: NAME=value verbatim, no quotes or interpolation; the environment wins.
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            name, _, value = line.partition("=")
            os.environ.setdefault(name.strip(), value)
