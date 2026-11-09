"""Server-rendered pages. Function views, so each reads top to bottom.

Every query goes through `published()`, and every page is 1-2 queries
(pinned by tests).
"""

from typing import TYPE_CHECKING

from django.db.models import F
from django.shortcuts import get_object_or_404, render

from catalog.models import Brand, Industry, Review, Status

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

HOME_LIST_SIZE = 6
# WordPress's brand page shows at most 100 reviews; the count comes from
# review_count, so it stays right past that.
BRAND_PAGE_REVIEW_LIMIT = 100


def home(request: HttpRequest) -> HttpResponse:
    featured_brands = (
        Brand.objects.published()
        .select_related("industry")
        # Unrated brands last: PostgreSQL puts NULLs first in DESC order.
        .order_by(F("average_rating").desc(nulls_last=True), "id")[:HOME_LIST_SIZE]
    )
    recent_reviews = (
        Review.objects.published()
        .filter(brand__status=Status.PUBLISH)
        .select_related("brand")
        .order_by("-published_at", "-id")[:HOME_LIST_SIZE]
    )
    return render(
        request,
        "catalog/home.html",
        {
            "featured_brands": featured_brands,
            "recent_reviews": recent_reviews,
        },
    )


def brand_list(request: HttpRequest) -> HttpResponse:
    """WordPress's brand archive. <BrandList /> renders the list in the browser
    from /api/brands/; the page passes it the industries for its filter."""
    industries = list(Industry.objects.order_by("name", "id").values("slug", "name"))
    return render(request, "catalog/brand_list.html", {"industries": industries})


def brand_detail(request: HttpRequest, slug: str) -> HttpResponse:
    brand = get_object_or_404(Brand.objects.published().select_related("industry"), slug=slug)
    reviews = (
        Review.objects.published()
        .filter(brand=brand)
        .order_by("-published_at", "-id")[:BRAND_PAGE_REVIEW_LIMIT]
    )
    return render(request, "catalog/brand_detail.html", {"brand": brand, "reviews": reviews})


def review_detail(request: HttpRequest, slug: str) -> HttpResponse:
    review = get_object_or_404(
        Review.objects.published()
        .filter(brand__status=Status.PUBLISH)
        .select_related("brand", "reviewer"),
        slug=slug,
    )
    return render(request, "catalog/review_detail.html", {"review": review})
