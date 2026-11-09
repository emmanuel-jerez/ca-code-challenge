"""manage.py import_wp_users: copy wp_users into the auth service. Safe to re-run."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from wp_import.errors import WpImportError
from wp_import.service import run_user_import, summarize
from wp_import.source import MariaDbSource, WpDbSettings


class Command(BaseCommand):
    help = (
        "Import WordPress users with no usable password and their mapped roles. "
        "Re-runnable: rows upsert on wp_user_id; passwords and roles set here are kept."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run every check and write, then roll back. Prints what would change.",
        )

    def handle(self, *args: object, **options: Any) -> None:  # noqa: ANN401 - Django's signature
        dry_run = bool(options["dry_run"])
        try:
            with MariaDbSource.connect(WpDbSettings.from_env()) as source:
                report = run_user_import(source, dry_run=dry_run)
        except WpImportError as error:
            raise CommandError(f"Import stopped, nothing was written: {error}") from error
        for line in summarize(report):
            self.stdout.write(line)
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: all changes rolled back."))
        else:
            self.stdout.write(self.style.SUCCESS("Import complete."))
