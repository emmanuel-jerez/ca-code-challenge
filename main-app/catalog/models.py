"""The brand-review domain: industries, brands, reviews and reviewers.

A clean relational model rather than WordPress's posts + postmeta shape. Rows
that came from WordPress carry their WordPress id under a unique constraint, so
the import can upsert on it (ADR 0007). Field choices are in ADRs 0019-0021 and
0026.
"""

from typing import Self
from urllib.parse import urlsplit

from django.db import models
from django.db.models import Q
from django.db.models.functions import Now
from django.utils.safestring import SafeString, mark_safe


class Status(models.TextChoices):
    """WordPress post statuses, plus one for rows WordPress no longer has.

    `auto-draft` is never imported, and revisions have their own post type.
    """

    PUBLISH = "publish"
    FUTURE = "future"
    DRAFT = "draft"
    PENDING = "pending"
    PRIVATE = "private"
    TRASH = "trash"
    REMOVED = "removed"


class SanitizedContent(models.Model):
    """Rows whose `content_html` was cleaned with nh3 at import."""

    content_html: str

    class Meta:
        abstract = True

    @property
    def body_html(self) -> SafeString:
        """The one place imported HTML skips autoescaping.

        `content_html` is only ever written by the import, which cleans it with
        nh3 and an allow-list (wp_import.content.to_safe_html). A test fails if
        a template uses |safe instead.
        """
        return mark_safe(self.content_html)  # noqa: S308 - nh3-sanitized at import


class PublishableQuerySet[M: models.Model](models.QuerySet[M]):
    def published(self) -> Self:
        """Rows the public site may show. Every page goes through this filter."""
        return self.filter(status=Status.PUBLISH)


class Industry(models.Model):
    wp_term_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)

    class Meta:
        verbose_name_plural = "industries"

    def __str__(self) -> str:
        return self.name


class Reviewer(models.Model):
    """A person who wrote reviews. The auth service owns the account (ADR 0020).

    Only the display name is cached here: no email, password or role.
    """

    wp_user_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True)
    # The auth service's `external_id` (the token's `sub`). Empty until the
    # auth service's id map is imported.
    auth_user_id = models.UUIDField(unique=True, null=True, blank=True)
    display_name = models.CharField(max_length=250)

    def __str__(self) -> str:
        return self.display_name


class Brand(SanitizedContent):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    # PROTECT: deleting an industry that still has brands must be a decision.
    industry = models.ForeignKey(Industry, on_delete=models.PROTECT, related_name="brands")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PUBLISH)

    # Raw WordPress HTML, never rendered. Kept so content can be re-cleaned
    # when the sanitizer allow-list changes (ADR 0026).
    content_source = models.TextField(blank=True)
    # nh3-cleaned at import. The only HTML templates may render.
    content_html = models.TextField(blank=True)
    # Card text. Set by the import only when the brand is created; after that
    # editors own it (ADR 0026).
    short_description = models.CharField(max_length=300, blank=True)

    website_url = models.URLField(max_length=500, blank=True)
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True)
    headquarters = models.CharField(max_length=200, blank=True)

    # Computed from published reviews at the end of each import (ADR 0019).
    # NULL means "not rated", not zero stars.
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    review_count = models.PositiveIntegerField(default=0)
    # WordPress's stored ACF value, kept for audit only. Wrong for 4 of 5 brands.
    legacy_average_rating = models.DecimalField(
        max_digits=2, decimal_places=1, null=True, blank=True
    )

    seo_title = models.CharField(max_length=300, blank=True)
    seo_description = models.CharField(max_length=500, blank=True)

    published_at = models.DateTimeField(null=True, blank=True)
    wp_modified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(auto_now=True)

    objects = PublishableQuerySet["Brand"].as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(founded_year__isnull=True)
                | Q(founded_year__gte=1800, founded_year__lte=2100),
                name="brand_founded_year_range",
            ),
            models.CheckConstraint(
                condition=Q(average_rating__isnull=True)
                | Q(average_rating__gte=1, average_rating__lte=5),
                name="brand_average_rating_range",
            ),
            models.CheckConstraint(
                condition=Q(legacy_average_rating__isnull=True)
                | Q(legacy_average_rating__gte=0, legacy_average_rating__lte=5),
                name="brand_legacy_average_rating_range",
            ),
            # Model validators don't run on save(), so the database itself
            # refuses javascript:, data: and ftp: links (CVE-2026-15920).
            models.CheckConstraint(
                condition=Q(website_url="")
                | Q(website_url__istartswith="http://")
                | Q(website_url__istartswith="https://"),
                name="brand_website_url_http",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def website_host(self) -> str:
        """The link text the theme shows: the URL's host name."""
        return urlsplit(self.website_url).hostname or ""


class Review(SanitizedContent):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True)
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=200, unique=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="reviews")
    # SET_NULL: the review stays readable through its name snapshot.
    reviewer = models.ForeignKey(
        Reviewer, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PUBLISH)

    # The name and location as displayed on this review. Location varies per
    # review for the same person, so it belongs here (ADR 0020).
    reviewer_name = models.CharField(max_length=100, blank=True)
    reviewer_location = models.CharField(max_length=100, blank=True)
    rating = models.PositiveSmallIntegerField()

    content_source = models.TextField(blank=True)
    content_html = models.TextField(blank=True)
    # Plain text for cards; autoescaped on output.
    content_text = models.TextField(blank=True)

    published_at = models.DateTimeField(null=True, blank=True)
    wp_modified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(auto_now=True)

    objects = PublishableQuerySet["Review"].as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_5"
            ),
        ]
        indexes = [
            # Brand page: a brand's reviews, newest first. The id tie-breaker
            # keeps the order stable (AGENTS.md).
            models.Index(fields=["brand", "-published_at", "-id"], name="review_brand_recent"),
            # Homepage: newest reviews overall.
            models.Index(fields=["-published_at", "-id"], name="review_recent"),
        ]

    def __str__(self) -> str:
        return self.title
