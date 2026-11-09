"""Reading WordPress users: the raw row type, the source Protocol, and the MariaDB source.

The import connects as its own read-only MariaDB user, which can read one
view and nothing else (db/initdb/03-wp-auth-import-user.sh). It never sees
`user_pass`, session tokens, or any other user meta (ADR 0024).
"""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import pymysql
import pymysql.cursors

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True, slots=True)
class RawWpUser:
    id: int
    login: str
    email: str
    # wp_capabilities as WordPress stores it: a PHP-serialized array.
    # None when the user has no capabilities row.
    capabilities: str | None


class WpUserSource(Protocol):
    def users(self) -> Iterator[RawWpUser]: ...


@dataclass(frozen=True, slots=True)
class WpDbSettings:
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> WpDbSettings:
        """Read from WP_IMPORT_DB_*. Only the auth import container gets these."""
        return cls(
            host=os.environ.get("WP_IMPORT_DB_HOST", "localhost"),
            port=int(os.environ.get("WP_IMPORT_DB_PORT", "3307")),
            database=os.environ.get("WP_IMPORT_DB_NAME", "wp"),
            user=os.environ.get("WP_IMPORT_DB_USER", "wp_auth_import"),
            password=os.environ.get("WP_IMPORT_DB_PASSWORD", ""),
        )


# The view joins wp_users to each user's wp_capabilities row. It's fixed in
# the init script, and identifiers can't be query parameters.
_USERS_SQL = "SELECT ID, user_login, user_email, capabilities FROM auth_import_users ORDER BY ID"


class MariaDbSource:
    """Reads the users view through PyMySQL (ADR 0007), in one read-only snapshot."""

    def __init__(
        self, connection: pymysql.connections.Connection[pymysql.cursors.DictCursor]
    ) -> None:
        self._connection = connection

    @classmethod
    @contextmanager
    def connect(cls, settings: WpDbSettings) -> Iterator[MariaDbSource]:
        connection = pymysql.connect(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password,
            database=settings.database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            yield cls(connection)
            connection.rollback()
        finally:
            connection.close()

    def users(self) -> Iterator[RawWpUser]:
        with self._connection.cursor() as cursor:
            cursor.execute(_USERS_SQL)
            rows = cursor.fetchall()
        for row in rows:
            capabilities = row["capabilities"]
            yield RawWpUser(
                id=_int(row["ID"]),
                login=str(row["user_login"]),
                email=str(row["user_email"]),
                capabilities=None if capabilities is None else str(capabilities),
            )


def _int(value: object) -> int:
    if isinstance(value, int):
        return value
    raise TypeError(f"expected an integer column, got {type(value).__name__}")
