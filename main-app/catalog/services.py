"""Domain operations other code calls."""

from django.db.models import Avg, Count, DecimalField, IntegerField, OuterRef, Subquery
from django.db.models.functions import Cast, Coalesce

from catalog.models import Brand, Review


def refresh_brand_ratings() -> int:
    """Recompute every brand's average_rating and review_count in one UPDATE.

    Counts published reviews only. A brand with none gets NULL ("not rated"),
    not zero. Anything that writes reviews must call this afterwards (ADR 0019).
    Returns the number of brands updated.
    """
    reviews = Review.objects.published().filter(brand=OuterRef("pk")).order_by().values("brand")
    return Brand.objects.update(
        review_count=Coalesce(
            Subquery(reviews.annotate(n=Count("pk")).values("n"), output_field=IntegerField()),
            0,
        ),
        # Cast rounds half away from zero to two places: 3.9166 becomes 3.92.
        average_rating=Subquery(
            reviews.annotate(
                avg=Cast(Avg("rating"), DecimalField(max_digits=3, decimal_places=2))
            ).values("avg")
        ),
    )
