"""Import WordPress users into the auth service. Safe to re-run (ADR 0024).

After cutover this service is the source of truth for accounts. So a re-run
adds users WordPress has and we don't, and follows a changed login or email,
but never touches a password, a role or `is_active`: those may have been
changed here since.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction

from accounts.models import User
from wp_import.errors import WpImportError
from wp_import.parse import parse_user

if TYPE_CHECKING:
    from wp_import.parse import WpUser
    from wp_import.source import WpUserSource


@dataclass
class UserImportReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    warnings: list[str] = field(default_factory=list)


class _DryRun(Exception):
    """Raised inside the transaction to roll a dry run back."""


def run_user_import(source: WpUserSource, *, dry_run: bool = False) -> UserImportReport:
    # Parse everything first: a bad row stops the run before any write.
    rows = [parse_user(raw) for raw in source.users()]
    report = UserImportReport()
    try:
        with transaction.atomic():
            _write(rows, report)
            if dry_run:
                raise _DryRun
    except _DryRun:
        pass
    except IntegrityError as error:
        # The case-insensitive unique constraints: a WordPress login or email
        # that an account created here already uses.
        raise WpImportError(
            f"a WordPress login or email is already used by another account: {error}"
        ) from error
    return report


def _write(rows: list[WpUser], report: UserImportReport) -> None:
    groups = {group.name: group for group in Group.objects.all()}
    existing = {
        user.wp_user_id: user
        for user in User.objects.filter(wp_user_id__in=[row.wp_user_id for row in rows])
    }
    for row in rows:
        for role in row.unmapped_roles:
            report.warnings.append(
                f"user {row.wp_user_id}: WordPress role {role!r} has no mapping; given no role"
            )
        user = existing.get(row.wp_user_id)
        if user is None:
            _create(row, groups)
            report.created += 1
        elif (user.username, user.email) != (row.username, row.email):
            user.username, user.email = row.username, row.email
            user.save(update_fields=["username", "email"])
            report.updated += 1
        else:
            report.unchanged += 1


def _create(row: WpUser, groups: dict[str, Group]) -> None:
    user = User(username=row.username, email=row.email, wp_user_id=row.wp_user_id)
    # The import never reads WordPress hashes; passwords are set with
    # `manage.py changepassword`, which runs the validators.
    user.set_unusable_password()
    user.save()
    user.groups.set([groups[role] for role in row.roles])


def summarize(report: UserImportReport) -> list[str]:
    lines = [
        f"users: {report.created} created, {report.updated} updated, {report.unchanged} unchanged"
    ]
    lines.extend(f"warning: {warning}" for warning in report.warnings)
    return lines
