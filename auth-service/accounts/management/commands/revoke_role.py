"""manage.py revoke_role <username> <role>."""

from typing import Any

from accounts.management.commands._roles import RoleCommand


class Command(RoleCommand):
    help = "Take a role away from a user."

    def handle(self, *args: object, **options: Any) -> None:  # noqa: ANN401 - Django's signature
        user, group = self.find(options["username"], options["role"])
        user.groups.remove(group)
        self.done(f"{user.username} no longer has the role {group.name}.")
