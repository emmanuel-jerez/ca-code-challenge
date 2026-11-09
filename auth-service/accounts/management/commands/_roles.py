"""Shared parts of grant_role and revoke_role."""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError, CommandParser

from accounts.models import User


class RoleCommand(BaseCommand):
    """Looks up the user and the role; subclasses apply the change."""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("username", help="Username, any case.")
        parser.add_argument("role", help="A role (Group) name, e.g. reader or editor.")

    def find(self, username: str, role: str) -> tuple[User, Group]:
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            raise CommandError(f"No user named {username!r}.") from None
        try:
            group = Group.objects.get(name=role)
        except Group.DoesNotExist:
            known = ", ".join(Group.objects.order_by("name").values_list("name", flat=True))
            raise CommandError(f"No role {role!r}. Roles: {known}.") from None
        return user, group

    def done(self, message: str) -> None:
        # Tokens are verified locally and live 10 minutes (ADR 0016), so
        # tokens already issued keep their old scopes until they expire.
        self.stdout.write(
            self.style.SUCCESS(message)
            + " Takes effect on the user's next token, within 10 minutes."
        )
