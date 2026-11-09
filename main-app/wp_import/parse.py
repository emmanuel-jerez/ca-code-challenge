"""Checked import rows, parsed from raw WordPress rows.

Every check happens here, before anything is written. A row that doesn't fit
raises a WpRowError, which stops the run (ADR 0026).

WordPress data never becomes a keyword name: each field is copied explicitly
from a dataclass, never expanded from a dict with `**`. Every 2025-26 Django ORM
SQL injection needed outside-controlled keys expanded into kwargs.
"""

import html
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from catalog.models import Status
from wp_import.errors import InvalidValue, UnknownMetaKey, UnsafeUrl

if TYPE_CHECKING:
    from datetime import datetime

    from wp_import.source import RawPost, RawTerm, RawUser

# Postmeta triage (ADR 0021). Keys we read, and keys we know and drop. Any
# other key stops the import, because it means WordPress's schema changed.
BRAND_META = {
    "website_url",
    "founded_year",
    "headquarters",
    "average_rating",
    "_yoast_wpseo_title",
    "_yoast_wpseo_metadesc",
}
REVIEW_META = {"brand", "rating", "reviewer_name", "reviewer_location"}
# ACF's `_`-prefixed field-key pointers serve only its admin screens.
# _edit_lock and _edit_last are WordPress's editor bookkeeping, added whenever
# someone opens a post in wp-admin.
_EDITOR_META = {"_edit_lock", "_edit_last"}
BRAND_IGNORED_META = {
    "_website_url",
    "_founded_year",
    "_headquarters",
    "_average_rating",
} | _EDITOR_META
REVIEW_IGNORED_META = {"_brand", "_rating", "_reviewer_name", "_reviewer_location"} | _EDITOR_META

# Django's slug path converter is ASCII-only, so anything else would 404.
_SLUG = re.compile(r"^[a-z0-9-]{1,200}$")
_HTTP_URL = URLValidator(schemes=["http", "https"])
_STATUSES = {status.value for status in Status} - {Status.REMOVED.value}


@dataclass(frozen=True, slots=True)
class WpIndustry:
    wp_term_id: int
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class WpReviewer:
    wp_user_id: int
    display_name: str


@dataclass(frozen=True, slots=True)
class WpBrand:
    wp_id: int
    slug: str
    name: str
    status: Status
    content: str
    excerpt: str
    website_url: str
    founded_year: int | None
    headquarters: str
    legacy_average_rating: Decimal | None
    seo_title: str
    seo_description: str
    published_at: datetime | None
    modified_at: datetime | None


@dataclass(frozen=True, slots=True)
class WpReview:
    wp_id: int
    slug: str
    title: str
    status: Status
    content: str
    brand_wp_id: int
    author_wp_id: int | None
    rating: int
    reviewer_name: str
    reviewer_location: str
    published_at: datetime | None
    modified_at: datetime | None


def parse_industry(term: RawTerm) -> WpIndustry:
    return WpIndustry(
        wp_term_id=term.term_id,
        # WordPress stores term names HTML-escaped (_wp_specialchars).
        name=_text("industry", term.term_id, "name", html.unescape(term.name), 200, required=True),
        slug=_slug("industry", term.term_id, term.slug),
    )


def parse_reviewer(user: RawUser) -> WpReviewer:
    return WpReviewer(
        wp_user_id=user.id,
        # Display names are stored HTML-escaped too.
        display_name=_text(
            "user", user.id, "display_name", html.unescape(user.display_name), 250, required=True
        ),
    )


def parse_brand(post: RawPost) -> WpBrand:
    kind = "brand"
    _check_meta_keys(kind, post, BRAND_META, BRAND_IGNORED_META)
    meta = post.meta
    return WpBrand(
        wp_id=post.id,
        slug=_slug(kind, post.id, post.slug),
        name=_text(kind, post.id, "post_title", post.title, 200, required=True),
        status=_status(kind, post),
        content=post.content,
        excerpt=post.excerpt,
        website_url=_website_url(kind, post.id, meta.get("website_url", "")),
        founded_year=_founded_year(kind, post.id, meta.get("founded_year", "")),
        headquarters=_text(kind, post.id, "headquarters", meta.get("headquarters", ""), 200),
        legacy_average_rating=_legacy_rating(kind, post.id, meta.get("average_rating", "")),
        seo_title=_text(
            kind, post.id, "_yoast_wpseo_title", meta.get("_yoast_wpseo_title", ""), 300
        ),
        seo_description=_text(
            kind, post.id, "_yoast_wpseo_metadesc", meta.get("_yoast_wpseo_metadesc", ""), 500
        ),
        published_at=post.date_gmt,
        modified_at=post.modified_gmt,
    )


def parse_review(post: RawPost) -> WpReview:
    kind = "review"
    _check_meta_keys(kind, post, REVIEW_META, REVIEW_IGNORED_META)
    meta = post.meta
    return WpReview(
        wp_id=post.id,
        slug=_slug(kind, post.id, post.slug),
        title=_text(kind, post.id, "post_title", post.title, 300, required=True),
        status=_status(kind, post),
        content=post.content,
        brand_wp_id=_positive_int(kind, post.id, "brand", meta.get("brand", "")),
        # post_author 0 means "no author".
        author_wp_id=post.author_id or None,
        rating=_rating(kind, post.id, meta.get("rating", "")),
        reviewer_name=_text(kind, post.id, "reviewer_name", meta.get("reviewer_name", ""), 100),
        reviewer_location=_text(
            kind, post.id, "reviewer_location", meta.get("reviewer_location", ""), 100
        ),
        published_at=post.date_gmt,
        modified_at=post.modified_gmt,
    )


def _check_meta_keys(kind: str, post: RawPost, read: set[str], ignored: set[str]) -> None:
    unknown = sorted(set(post.meta) - read - ignored)
    if unknown:
        raise UnknownMetaKey(kind, post.id, f"untriaged postmeta keys {unknown}")


def _status(kind: str, post: RawPost) -> Status:
    if post.password:
        raise InvalidValue(kind, post.id, "is password-protected; the model has no such state")
    if post.status not in _STATUSES:
        raise InvalidValue(kind, post.id, f"unexpected post_status {post.status!r}")
    return Status(post.status)


def _slug(kind: str, wp_id: int, value: str) -> str:
    if not _SLUG.fullmatch(value):
        raise InvalidValue(
            kind, wp_id, f"slug {value!r} isn't lowercase ASCII letters, digits and hyphens"
        )
    return value


def _text(
    kind: str, wp_id: int, field: str, value: str, max_length: int, *, required: bool = False
) -> str:
    value = value.strip()
    if required and not value:
        raise InvalidValue(kind, wp_id, f"{field} is empty")
    if len(value) > max_length:
        raise InvalidValue(kind, wp_id, f"{field} is longer than {max_length} characters")
    return value


def _positive_int(kind: str, wp_id: int, field: str, value: str) -> int:
    if not value.isdigit() or int(value) == 0:
        raise InvalidValue(kind, wp_id, f"{field} {value!r} isn't a positive integer")
    return int(value)


def _rating(kind: str, wp_id: int, value: str) -> int:
    if value not in {"1", "2", "3", "4", "5"}:
        raise InvalidValue(kind, wp_id, f"rating {value!r} isn't a whole number from 1 to 5")
    return int(value)


def _founded_year(kind: str, wp_id: int, value: str) -> int | None:
    if not value.strip():
        return None
    if not value.strip().isdigit() or not 1800 <= int(value) <= 2100:
        raise InvalidValue(kind, wp_id, f"founded_year {value!r} isn't a year from 1800 to 2100")
    return int(value)


def _legacy_rating(kind: str, wp_id: int, value: str) -> Decimal | None:
    if not value.strip():
        return None
    try:
        rating = Decimal(value.strip())
    except InvalidOperation:
        rating = Decimal("NaN")
    if not rating.is_finite() or not 0 <= rating <= 5:
        raise InvalidValue(kind, wp_id, f"average_rating {value!r} isn't a number from 0 to 5")
    return rating.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _website_url(kind: str, wp_id: int, value: str) -> str:
    """http or https only. Django doesn't run URLField validators on save()."""
    value = value.strip()
    if not value:
        return ""
    if len(value) > 500:
        raise InvalidValue(kind, wp_id, "website_url is longer than 500 characters")
    try:
        _HTTP_URL(value)
    except ValidationError:
        raise UnsafeUrl(kind, wp_id, f"website_url {value!r} isn't an http(s) URL") from None
    return value
