"""The brand listing's query string: validated, then turned into a queryset.

Request values are only ever dictionary keys here. What reaches order_by()
is an expression written in this file, so client input never names a column
(ADR 0022; CVE-2026-1312 came in through order_by()).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Self

from django.db.models import F, OrderBy, Prefetch
from rest_framework import serializers

from catalog.models import Brand, Industry, Review

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import QueryDict


class Ordering(StrEnum):
    RATING_DESC = "-average_rating"
    RATING_ASC = "average_rating"
    REVIEW_COUNT_DESC = "-review_count"
    REVIEW_COUNT_ASC = "review_count"


# Every ordering ends in the unique id, so pages never repeat or skip rows.
# Unrated brands (NULL) go last both ways: PostgreSQL would put them first
# in descending order.
ORDER_BY: dict[Ordering, tuple[OrderBy | str, ...]] = {
    Ordering.RATING_DESC: (
        F("average_rating").desc(nulls_last=True),
        "-review_count",
        "id",
    ),
    Ordering.RATING_ASC: (F("average_rating").asc(nulls_last=True), "id"),
    # Every brand in the WordPress data has 12 reviews, so name decides
    # these in practice.
    Ordering.REVIEW_COUNT_DESC: ("-review_count", "name", "id"),
    Ordering.REVIEW_COUNT_ASC: ("review_count", "name", "id"),
}


# The attribute the prefetch below sets on each brand: a list of 0 or 1 reviews.
TOP_REVIEWS = "top_reviews"

MAX_INDUSTRIES = 10
DEFAULT_PAGE_SIZE = 12
MAX_PAGE_SIZE = 50


@dataclass(frozen=True, slots=True)
class BrandListQuery:
    """A validated query string. Built only by BrandListQuerySerializer."""

    # Empty means every industry.
    industries: frozenset[str]
    ordering: Ordering
    page_size: int


class BrandListQuerySerializer(serializers.Serializer[BrandListQuery]):
    """Checks the query string before the listing query is built.

    Parameters it doesn't know are ignored, so a newer client still works
    against an older server during a rollout. Known ones are strict: a bad
    value is a 400, never a silent fallback. Build it with
    from_query_params().
    """

    # Repeated keys (?industry=a&industry=b), meaning any of them. No child
    # field: DRF's default passes each value through as sent (query values
    # are always strings), and validate_industry checks it against the
    # database. A per-item field would trim values and key its errors by
    # position ({"industry": {"0": [...]}}), breaking the one-message shape.
    industry = serializers.ListField(max_length=MAX_INDUSTRIES, default=list)
    ordering = serializers.ChoiceField(choices=list(Ordering), default=Ordering.RATING_DESC)
    page_size = serializers.IntegerField(
        min_value=1, max_value=MAX_PAGE_SIZE, default=DEFAULT_PAGE_SIZE
    )

    @classmethod
    def from_query_params(cls, params: QueryDict) -> Self:
        """Validate a query string, treating an empty value as a value.

        Given a QueryDict, DRF reads "?ordering=" as "not sent" and applies
        the default. A plain dict holding only the keys actually sent makes
        "" a bad value (400) instead.
        """
        # A repeated scalar parameter uses its last value, as Django's
        # QueryDict does everywhere.
        data: dict[str, object] = {name: params[name] for name in params}
        data["industry"] = params.getlist("industry")
        return cls(data=data)

    def validate_industry(self, slugs: list[str]) -> frozenset[str]:
        wanted = frozenset(slugs)
        # Postgres rejects NUL in a string parameter, and no slug contains one.
        searchable = {slug for slug in wanted if "\x00" not in slug}
        known = set(Industry.objects.filter(slug__in=searchable).values_list("slug", flat=True))
        # Sorted so the message names the same slug every time.
        unknown = sorted(wanted - known)
        if unknown:
            raise serializers.ValidationError(f'Unknown industry: "{unknown[0]}".')
        return wanted

    def to_query(self) -> BrandListQuery:
        data = self.validated_data
        return BrandListQuery(
            industries=data["industry"],
            ordering=Ordering(data["ordering"]),
            page_size=data["page_size"],
        )


def brand_cards(query: BrandListQuery) -> QuerySet[Brand]:
    """Published brands for the listing, filtered and ordered as asked."""
    brands = (
        Brand.objects.published()
        .select_related("industry")
        # Card fields only, not the HTML bodies.
        .only(
            "slug",
            "name",
            "industry__slug",
            "industry__name",
            "average_rating",
            "review_count",
            "short_description",
        )
        .prefetch_related(Prefetch("reviews", queryset=_top_review(), to_attr=TOP_REVIEWS))
    )
    if query.industries:
        # A foreign key, so the join can't duplicate brands (ADR 0026).
        brands = brands.filter(industry__slug__in=query.industries)
    return brands.order_by(*ORDER_BY[query.ordering])


def _top_review() -> QuerySet[Review]:
    """Each brand's top review: highest rating, then newest, then last added.

    "Top" means best, so a 3-star brand still quotes its best review; the
    alternative (the review closest to the brand's average) is in ADR 0027.
    A sliced prefetch: Django fetches it for the whole page in one query,
    with ROW_NUMBER() OVER (PARTITION BY brand_id ...).
    """
    return (
        Review.objects.published()
        .order_by("-rating", F("published_at").desc(nulls_last=True), "-id")
        # Card fields only, not the HTML bodies. brand is needed to match
        # reviews to brands.
        .only("brand", "slug", "title", "rating", "reviewer_name", "content_text")[:1]
    )
