"""The JSON API. Function views, like the pages (ADR 0026)."""

from typing import TYPE_CHECKING

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.serializers import ListSerializer

from catalog.api.query import BrandListQuerySerializer, brand_cards
from catalog.api.serializers import BrandCardSerializer
from catalog.models import Brand

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response


class BrandPagination(PageNumberPagination):
    """DRF's page-number envelope, with the page size already validated.

    page_size_query_param stays unset: BrandListQuerySerializer is the only
    parser of ?page_size, so a value it rejects can't be clamped or
    replaced here. ?page stays DRF's: a page past the end is a 404.
    """

    def __init__(self, page_size: int) -> None:
        self.page_size = page_size


@api_view(["GET"])
# Public, and never reads the Authorization header: an expired token must not
# turn the public listing into a 401.
@authentication_classes([])
@permission_classes([AllowAny])
def brand_list(request: Request) -> Response:
    params = BrandListQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    query = params.to_query()
    brands = brand_cards(query)
    paginator = BrandPagination(query.page_size)
    # None only when a paginator has no page size; this one always has one.
    page = paginator.paginate_queryset(brands, request) or []
    cards = ListSerializer[list[Brand]](page, child=BrandCardSerializer())
    return paginator.get_paginated_response(cards.data)
