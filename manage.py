#!/usr/bin/env python
import os
import sys
from pathlib import Path


def main():
    from ribcage import environment

    # Local runs read a gitignored .env; the image has none, so the host's environment is all there is (#45).
    environment.load_file(Path(__file__).resolve().parent / ".env")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ribcage.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
