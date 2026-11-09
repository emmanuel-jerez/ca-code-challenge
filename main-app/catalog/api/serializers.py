"""What one brand card looks like on the wire.

Plain serializers rather than ModelSerializer, so every field and its JSON
type is written out here, and a model change can't silently change the
contract the frontend's Zod schema checks (ADR 0010).
"""

from typing import TYPE_CHECKING

from django.utils.text import Truncator
from rest_framework import serializers

from catalog.api.query import TOP_REVIEWS
from catalog.models import Brand, Review

if TYPE_CHECKING:
    from rest_framework.utils.serializer_helpers import ReturnDict

SNIPPET_LENGTH = 160


class IndustrySerializer(serializers.Serializer[object]):
    slug = serializers.SlugField()
    name = serializers.CharField()


class TopReviewSerializer(serializers.Serializer[Review]):
    slug = serializers.SlugField()
    title = serializers.CharField()
    rating = serializers.IntegerField()
    reviewer_name = serializers.CharField()
    # Plain text, never HTML: clients render it as text, and Django
    # autoescapes it.
    snippet = serializers.SerializerMethodField()

    def get_snippet(self, review: Review) -> str:
        # Cut plain text only. Truncator's html=True is CVE-2026-1285's
        # quadratic path.
        return Truncator(review.content_text).chars(SNIPPET_LENGTH)


class BrandCardSerializer(serializers.Serializer[Brand]):
    slug = serializers.SlugField()
    name = serializers.CharField()
    industry = IndustrySerializer()
    # A JSON number (3.92), not DRF's default string ("3.92"). null means the
    # brand has no published reviews yet (ADR 0019).
    average_rating = serializers.DecimalField(
        max_digits=3, decimal_places=2, coerce_to_string=False, allow_null=True
    )
    review_count = serializers.IntegerField()
    short_description = serializers.CharField()
    top_review = serializers.SerializerMethodField()

    def get_top_review(self, brand: Brand) -> ReturnDict[str, object] | None:
        # Set by brand_cards()'s prefetch. getattr because the attribute
        # exists only on brands loaded through it; the annotation states what
        # Prefetch(to_attr=...) always stores there, a list of reviews.
        top: list[Review] = getattr(brand, TOP_REVIEWS)
        return TopReviewSerializer(top[0]).data if top else None


class StrictCharField(serializers.CharField):
    """A CharField that refuses numbers instead of turning 5 into "5"."""

    def to_internal_value(self, data: object) -> str:
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class BrandEditSerializer(serializers.Serializer[dict[str, str]]):
    """The PATCH body: only the short description is editable (ADR 0034).

    Plain text, never HTML: templates autoescape it and <BrandList /> renders
    it as text, so nothing needs sanitizing.
    """

    # The column's limit. Trimmed (DRF's default), so "   " is blank.
    short_description = StrictCharField(max_length=300)

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        # DRF ignores unknown keys; refuse them, so a client that thinks it
        # changed the name hears that it didn't.
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {name: "This field can't be edited." for name in sorted(unknown)}
            )
        return attrs
