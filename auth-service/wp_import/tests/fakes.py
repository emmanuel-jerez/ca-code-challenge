"""An in-memory WordPress that satisfies the WpUserSource Protocol."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from wp_import.source import RawWpUser

if TYPE_CHECKING:
    from collections.abc import Iterator


def capabilities(*roles: str) -> str:
    """wp_capabilities as WordPress serializes it."""
    entries = "".join(f's:{len(role)}:"{role}";b:1;' for role in roles)
    return f"a:{len(roles)}:{{{entries}}}"


@dataclass
class FakeWordPress:
    people: list[RawWpUser] = field(default_factory=list)

    def users(self) -> Iterator[RawWpUser]:
        yield from self.people

    def add_user(
        self,
        wp_id: int,
        login: str | None = None,
        *,
        email: str | None = None,
        roles: tuple[str, ...] = ("subscriber",),
    ) -> None:
        login = login or f"user{wp_id}"
        self.people.append(
            RawWpUser(
                id=wp_id,
                login=login,
                email=email or f"{login}@example.com",
                capabilities=capabilities(*roles),
            )
        )
