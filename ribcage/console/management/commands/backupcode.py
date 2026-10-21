import os
import sqlite3
from datetime import UTC, datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django.utils import timezone

from ribcage.operations import offer
from ribcage.operations.backup import BackupFailed, describe, row_counts


class Command(BaseCommand):
    help = "Make a one-time code for the admin's backup page, run in the ribcage container's terminal (#68)."

    def add_arguments(self, parser):
        # What the code is for; the upload joins download here (#81).
        parser.add_argument("purpose", choices=[offer.DOWNLOAD])

    def handle(self, *args, **options):
        if getattr(os, "geteuid", lambda: None)() == 0:
            raise CommandError("Run this as the image's user, not root: a root-owned offer can't be served or replaced (#68).")
        now = datetime.now(UTC)
        try:
            code, backup_file = offer.offer_download(settings.DATABASES["default"]["NAME"], settings.BACKUP_OFFER_DIRECTORY, now)
        except (BackupFailed, sqlite3.Error) as error:
            raise CommandError(f"No backup offered: {error}") from error
        until = timezone.localtime(now + offer.LIFETIME)
        self.stdout.write(f"Offered {backup_file.name}: {describe(row_counts(backup_file))}.")
        self.stdout.write(f"Code: {code}")
        self.stdout.write(
            f"Enter it at {reverse('console_backup')} by {until:%H:%M} {settings.TIME_ZONE}. It works once, and a wrong code voids it."
        )
