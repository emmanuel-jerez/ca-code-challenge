"""manage.py grant_role <username> <role>."""

from typing import Any

from accounts.management.commands._roles import RoleCommand


class Command(RoleCommand):
    help = "Give a user a role. The auth service is the only place roles change."

    def handle(self, *args: object, **options: Any) -> None:  # noqa: ANN401 - Django's signature
        user, group = self.find(options["username"], options["role"])
        user.groups.add(group)
        self.done(f"{user.username} now has the role {group.name}.")
