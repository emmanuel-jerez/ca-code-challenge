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
    page_size = 12


@api_view(["GET"])
# Public, and never reads the Authorization header: an expired token must not
# turn the public listing into a 401.
@authentication_classes([])
@permission_classes([AllowAny])
def brand_list(request: Request) -> Response:
    params = BrandListQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    brands = brand_cards(params.to_query())
    paginator = BrandPagination()
    # None only when a paginator has no page size; this one always has one.
    page = paginator.paginate_queryset(brands, request) or []
    cards = ListSerializer[list[Brand]](page, child=BrandCardSerializer())
    return paginator.get_paginated_response(cards.data)
