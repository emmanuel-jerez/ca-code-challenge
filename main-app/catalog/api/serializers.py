"""What one brand card looks like on the wire.

Plain serializers rather than ModelSerializer, so every field and its JSON
type is written out here, and a model change can't silently change the
contract the frontend's Zod schema checks (ADR 0010).
"""

from rest_framework import serializers

from catalog.models import Brand


class IndustrySerializer(serializers.Serializer[object]):
    slug = serializers.SlugField()
    name = serializers.CharField()


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

    def get_top_review(self, brand: Brand) -> None:
        return None
