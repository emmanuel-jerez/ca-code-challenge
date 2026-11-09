"""Which scopes a user's roles grant. Roles are Django Groups (ADR 0033)."""

from typing import TYPE_CHECKING

from accounts.models import Scope

if TYPE_CHECKING:
    from accounts.models import User


def scopes_for(user: User) -> list[str]:
    """The union of the user's roles' scopes, sorted so tokens are stable."""
    names = Scope.objects.filter(groups__user=user).values_list("name", flat=True)
    return sorted(set(names))
