"""The brand listing's query string: validated, then turned into a queryset.

Request values are only ever dictionary keys here. What reaches order_by()
is an expression written in this file, so client input never names a column
(ADR 0022; CVE-2026-1312 came in through order_by()).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from django.db.models import F, OrderBy
from rest_framework import serializers

from catalog.models import Brand

if TYPE_CHECKING:
    from django.db.models import QuerySet


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


@dataclass(frozen=True, slots=True)
class BrandListQuery:
    """A validated query string. Built only by BrandListQuerySerializer."""

    ordering: Ordering


class BrandListQuerySerializer(serializers.Serializer[BrandListQuery]):
    """Checks the query string before anything touches the database.

    Parameters it doesn't know are ignored, so a newer client still works
    against an older server during a rollout. Known ones are strict: a bad
    value is a 400, never a silent fallback.
    """

    ordering = serializers.ChoiceField(choices=list(Ordering), default=Ordering.RATING_DESC)

    def to_query(self) -> BrandListQuery:
        data = self.validated_data
        return BrandListQuery(ordering=Ordering(data["ordering"]))


def brand_cards(query: BrandListQuery) -> QuerySet[Brand]:
    """Published brands for the listing, filtered and ordered as asked."""
    return Brand.objects.published().select_related("industry").order_by(*ORDER_BY[query.ordering])
