"""Reading WordPress: raw row types, the source Protocol, and the MariaDB source.

Rows leave this module as frozen dataclasses with WordPress's own values,
still unvalidated. `parse.py` turns them into checked import rows.
"""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, Protocol

import pymysql
import pymysql.cursors

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

type PostType = Literal["brand", "review"]


@dataclass(frozen=True, slots=True)
class RawTerm:
    term_id: int
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class RawTermLink:
    """One row of wp_term_relationships: a post tagged with a term."""

    object_id: int
    term_id: int


@dataclass(frozen=True, slots=True)
class RawUser:
    id: int
    display_name: str


@dataclass(frozen=True, slots=True)
class RawPost:
    id: int
    slug: str
    title: str
    content: str
    excerpt: str
    status: str
    password: str
    author_id: int
    date_gmt: datetime | None
    modified_gmt: datetime | None
    # One value per key. WordPress allows duplicate keys; like
    # get_post_meta($id, $key, true), the lowest meta_id wins.
    meta: Mapping[str, str]


class WpSource(Protocol):
    """Everything the import reads from WordPress, one method per kind of row."""

    def industries(self) -> Iterator[RawTerm]: ...
    def industry_links(self) -> Iterator[RawTermLink]: ...
    def users(self) -> Iterator[RawUser]: ...
    def posts(self, post_type: PostType) -> Iterator[RawPost]: ...


@dataclass(frozen=True, slots=True)
class WpDbSettings:
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> WpDbSettings:
        """Read from WP_IMPORT_DB_*. Only the import container gets these."""
        return cls(
            host=os.environ.get("WP_IMPORT_DB_HOST", "localhost"),
            port=int(os.environ.get("WP_IMPORT_DB_PORT", "3307")),
            database=os.environ.get("WP_IMPORT_DB_NAME", "wp"),
            user=os.environ.get("WP_IMPORT_DB_USER", "wp_import"),
            password=os.environ.get("WP_IMPORT_DB_PASSWORD", ""),
        )


def _as_utc(value: object) -> datetime | None:
    """WordPress GMT columns are naive UTC. Zero dates come back as non-datetimes."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC)
    return None


# Table names are fixed: the read-only user is granted exactly these tables,
# and identifiers can't be query parameters. Every value is a %s parameter,
# and every parameter is a scalar (PyMySQL's 1.2.4 fix concerns sequences).
_POSTS_SQL = """
    SELECT ID, post_name, post_title, post_content, post_excerpt, post_status,
           post_password, post_author, post_date_gmt, post_modified_gmt
    FROM wp_posts
    WHERE post_type = %s AND post_status <> 'auto-draft' AND ID > %s
    ORDER BY ID
    LIMIT %s
"""
_META_SQL = """
    SELECT post_id, meta_key, meta_value
    FROM wp_postmeta
    WHERE post_id BETWEEN %s AND %s
    ORDER BY meta_id
"""
_INDUSTRIES_SQL = """
    SELECT t.term_id, t.name, t.slug
    FROM wp_terms t
    JOIN wp_term_taxonomy tt ON tt.term_id = t.term_id
    WHERE tt.taxonomy = 'industry'
    ORDER BY t.term_id
"""
_INDUSTRY_LINKS_SQL = """
    SELECT tr.object_id, tt.term_id
    FROM wp_term_relationships tr
    JOIN wp_term_taxonomy tt ON tt.term_taxonomy_id = tr.term_taxonomy_id
    WHERE tt.taxonomy = 'industry'
    ORDER BY tr.object_id, tt.term_id
"""
# The import user can read only these two columns of wp_users.
_USERS_SQL = "SELECT ID, display_name FROM wp_users ORDER BY ID"


class MariaDbSource:
    """Reads WordPress's MariaDB through PyMySQL (ADR 0007).

    Posts are read in keyset-paginated batches (`ID > last ORDER BY ID`) inside
    one consistent, read-only snapshot, so every table is read as of the same
    moment even if someone edits WordPress mid-import.
    """

    def __init__(
        self,
        connection: pymysql.connections.Connection[pymysql.cursors.DictCursor],
        batch_size: int = 500,
    ) -> None:
        self._connection = connection
        self._batch_size = batch_size

    @classmethod
    @contextmanager
    def connect(cls, settings: WpDbSettings) -> Iterator[MariaDbSource]:
        connection = pymysql.connect(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password,
            database=settings.database,
            # utf8mb4 only: PyMySQL calls other charsets legacy after its
            # 1.2.1 multibyte escaping fix.
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

    def _rows(self, sql: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    def industries(self) -> Iterator[RawTerm]:
        for row in self._rows(_INDUSTRIES_SQL):
            yield RawTerm(
                term_id=_int(row["term_id"]), name=str(row["name"]), slug=str(row["slug"])
            )

    def industry_links(self) -> Iterator[RawTermLink]:
        for row in self._rows(_INDUSTRY_LINKS_SQL):
            yield RawTermLink(object_id=_int(row["object_id"]), term_id=_int(row["term_id"]))

    def users(self) -> Iterator[RawUser]:
        for row in self._rows(_USERS_SQL):
            yield RawUser(id=_int(row["ID"]), display_name=str(row["display_name"]))

    def posts(self, post_type: PostType) -> Iterator[RawPost]:
        last_id = 0
        while True:
            batch = self._rows(_POSTS_SQL, (post_type, last_id, self._batch_size))
            if not batch:
                return
            first_id, last_id = _int(batch[0]["ID"]), _int(batch[-1]["ID"])
            meta: dict[int, dict[str, str]] = {}
            for row in self._rows(_META_SQL, (first_id, last_id)):
                # setdefault keeps the first value seen, i.e. the lowest meta_id.
                meta.setdefault(_int(row["post_id"]), {}).setdefault(
                    str(row["meta_key"]), str(row["meta_value"] or "")
                )
            for row in batch:
                post_id = _int(row["ID"])
                yield RawPost(
                    id=post_id,
                    slug=str(row["post_name"]),
                    title=str(row["post_title"]),
                    content=str(row["post_content"]),
                    excerpt=str(row["post_excerpt"]),
                    status=str(row["post_status"]),
                    password=str(row["post_password"]),
                    author_id=_int(row["post_author"]),
                    date_gmt=_as_utc(row["post_date_gmt"]),
                    modified_gmt=_as_utc(row["post_modified_gmt"]),
                    meta=meta.get(post_id, {}),
                )


def _int(value: object) -> int:
    if isinstance(value, int):
        return value
    raise TypeError(f"expected an integer column, got {type(value).__name__}")
