"""The re-runnable WordPress import (ADRs 0007, 0019-0021, 0026).

1. Read and parse everything. Any bad row stops the run before a write.
2. In one transaction, behind an advisory lock: upsert industries, reviewers,
   brands and reviews on their WordPress ids. Rows whose stored values already
   match are not written, so a second run writes nothing and says so.
3. Mark rows WordPress no longer has as `removed`, then recompute ratings.

A dry run does all of it, then rolls back.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db import connection, models, transaction

from catalog.models import Brand, Industry, Review, Reviewer, Status
from catalog.services import refresh_brand_ratings
from wp_import.content import first_words, has_shortcode, to_plain_text, to_safe_html
from wp_import.errors import BadReference, ImportAlreadyRunning
from wp_import.parse import (
    WpBrand,
    WpIndustry,
    WpReview,
    WpReviewer,
    parse_brand,
    parse_industry,
    parse_review,
    parse_reviewer,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from wp_import.source import WpSource

# pg_try_advisory_xact_lock key shared by every import run. Any constant works,
# as long as nothing else in this database uses it.
IMPORT_LOCK_KEY = 2026_11_09_01
# The theme's card text is the first 22 words of the body (front-page.php).
SHORT_DESCRIPTION_WORDS = 22


@dataclass
class Counts:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0

    def __str__(self) -> str:
        return (
            f"{self.created} created, {self.updated} updated, "
            f"{self.unchanged} unchanged, {self.removed} removed"
        )


@dataclass
class ImportReport:
    industries: Counts = field(default_factory=Counts)
    reviewers: Counts = field(default_factory=Counts)
    brands: Counts = field(default_factory=Counts)
    reviews: Counts = field(default_factory=Counts)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Parsed:
    industries: list[WpIndustry]
    brand_industry: dict[int, int]
    reviewers: list[WpReviewer]
    brands: list[WpBrand]
    reviews: list[WpReview]


def run_import(source: WpSource, *, dry_run: bool = False) -> ImportReport:
    parsed = _read(source)
    report = ImportReport()
    with transaction.atomic():
        _lock()
        industry_pks = _write_industries(parsed.industries, report.industries)
        reviewer_pks = _write_reviewers(parsed.reviewers, report.reviewers)
        brand_pks = _write_brands(parsed, industry_pks, report)
        _write_reviews(parsed.reviews, brand_pks, reviewer_pks, report)
        report.brands.removed = _mark_removed(Brand, set(brand_pks))
        report.reviews.removed = _mark_removed(Review, {r.wp_id for r in parsed.reviews})
        refresh_brand_ratings()
        if dry_run:
            transaction.set_rollback(True)
    return report


def _read(source: WpSource) -> _Parsed:
    industries = [parse_industry(term) for term in source.industries()]
    known_terms = {industry.wp_term_id for industry in industries}
    brands = [parse_brand(post) for post in source.posts("brand")]
    reviews = [parse_review(post) for post in source.posts("review")]

    # Exactly one industry per brand (ADR 0026): fail loudly rather than pick one.
    terms_by_brand: dict[int, list[int]] = {}
    for link in source.industry_links():
        if link.term_id in known_terms:
            terms_by_brand.setdefault(link.object_id, []).append(link.term_id)
    brand_industry: dict[int, int] = {}
    for brand in brands:
        terms = terms_by_brand.get(brand.wp_id, [])
        if len(terms) != 1:
            raise BadReference(
                "brand", brand.wp_id, f"has {len(terms)} industries; the model allows exactly one"
            )
        brand_industry[brand.wp_id] = terms[0]

    brand_ids = {brand.wp_id for brand in brands}
    for review in reviews:
        if review.brand_wp_id not in brand_ids:
            raise BadReference(
                "review", review.wp_id, f"points at brand {review.brand_wp_id}, which isn't a brand"
            )

    # Only people who wrote reviews become reviewers (ADR 0020).
    authors = {review.author_wp_id for review in reviews}
    reviewers = [parse_reviewer(user) for user in source.users() if user.id in authors]
    return _Parsed(industries, brand_industry, reviewers, brands, reviews)


def _lock() -> None:
    """Stop two imports from running at once. Released at commit or rollback."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [IMPORT_LOCK_KEY])
        row = cursor.fetchone()
    if not row or row[0] is not True:
        raise ImportAlreadyRunning


def _upsert[M: models.Model](
    model: type[M],
    existing: Mapping[int, M],
    key_field: str,
    key: int,
    values: dict[str, object],
    counts: Counts,
    create_only: dict[str, object] | None = None,
) -> int:
    """Create or update one row keyed on its WordPress id; skip it if unchanged.

    `values` keys are literal field names written in this module, never keys
    taken from WordPress. Returns the row's primary key.
    """
    current = existing.get(key)
    if current is not None and all(getattr(current, f) == v for f, v in values.items()):
        counts.unchanged += 1
        return _pk(current)
    obj, created = model._default_manager.update_or_create(
        defaults=values,
        create_defaults={**values, **(create_only or {})},
        **{key_field: key},
    )
    if created:
        counts.created += 1
    else:
        counts.updated += 1
    return _pk(obj)


def _pk(obj: models.Model) -> int:
    # django-stubs types `pk` as Any; every model here has a BigAutoField id.
    if not isinstance(obj.pk, int):
        raise TypeError(f"{type(obj).__name__} has no integer primary key")
    return obj.pk


def _write_industries(rows: list[WpIndustry], counts: Counts) -> dict[int, int]:
    existing = Industry.objects.in_bulk([r.wp_term_id for r in rows], field_name="wp_term_id")
    return {
        row.wp_term_id: _upsert(
            Industry,
            existing,
            "wp_term_id",
            row.wp_term_id,
            {"name": row.name, "slug": row.slug},
            counts,
        )
        for row in rows
    }


def _write_reviewers(rows: list[WpReviewer], counts: Counts) -> dict[int, int]:
    existing = Reviewer.objects.in_bulk([r.wp_user_id for r in rows], field_name="wp_user_id")
    return {
        row.wp_user_id: _upsert(
            Reviewer,
            existing,
            "wp_user_id",
            row.wp_user_id,
            {"display_name": row.display_name},
            counts,
        )
        for row in rows
    }


def _write_brands(
    parsed: _Parsed, industry_pks: dict[int, int], report: ImportReport
) -> dict[int, int]:
    existing = Brand.objects.in_bulk([b.wp_id for b in parsed.brands], field_name="wp_id")
    pks: dict[int, int] = {}
    for row in parsed.brands:
        if has_shortcode(row.content):
            report.warnings.append(f"brand {row.wp_id}: shortcode left as literal text")
        values: dict[str, object] = {
            "name": row.name,
            "slug": row.slug,
            "industry_id": industry_pks[parsed.brand_industry[row.wp_id]],
            "status": row.status,
            "content_source": row.content,
            "content_html": to_safe_html(row.content),
            "website_url": row.website_url,
            "founded_year": row.founded_year,
            "headquarters": row.headquarters,
            "legacy_average_rating": row.legacy_average_rating,
            "seo_title": row.seo_title,
            "seo_description": row.seo_description,
            "published_at": row.published_at,
            "wp_modified_at": row.modified_at,
        }
        # Editors own the short description once the brand exists, so a
        # re-import must never overwrite it (ADR 0026).
        short = first_words(
            to_plain_text(row.excerpt or row.content), SHORT_DESCRIPTION_WORDS, max_length=300
        )
        pks[row.wp_id] = _upsert(
            Brand,
            existing,
            "wp_id",
            row.wp_id,
            values,
            report.brands,
            create_only={"short_description": short},
        )
    return pks


def _write_reviews(
    rows: list[WpReview],
    brand_pks: dict[int, int],
    reviewer_pks: dict[int, int],
    report: ImportReport,
) -> None:
    existing = Review.objects.in_bulk([r.wp_id for r in rows], field_name="wp_id")
    for row in rows:
        if has_shortcode(row.content):
            report.warnings.append(f"review {row.wp_id}: shortcode left as literal text")
        reviewer_pk = reviewer_pks.get(row.author_wp_id) if row.author_wp_id else None
        values: dict[str, object] = {
            "title": row.title,
            "slug": row.slug,
            "brand_id": brand_pks[row.brand_wp_id],
            "reviewer_id": reviewer_pk,
            "status": row.status,
            "reviewer_name": row.reviewer_name,
            "reviewer_location": row.reviewer_location,
            "rating": row.rating,
            "content_source": row.content,
            "content_html": to_safe_html(row.content),
            "content_text": to_plain_text(row.content),
            "published_at": row.published_at,
            "wp_modified_at": row.modified_at,
        }
        _upsert(Review, existing, "wp_id", row.wp_id, values, report.reviews)


def _mark_removed(model: type[Brand] | type[Review], seen_wp_ids: set[int]) -> int:
    """Hide rows WordPress no longer has. Kept, not deleted (ADR 0026)."""
    return (
        model._default_manager.filter(wp_id__isnull=False)
        .exclude(wp_id__in=seen_wp_ids)
        .exclude(status=Status.REMOVED)
        .update(status=Status.REMOVED)
    )


def summarize(report: ImportReport) -> list[str]:
    lines = [
        f"{name}: {counts}"
        for name, counts in (
            ("industries", report.industries),
            ("reviewers", report.reviewers),
            ("brands", report.brands),
            ("reviews", report.reviews),
        )
    ]
    lines += [f"warning: {w}" for w in report.warnings]
    return lines
