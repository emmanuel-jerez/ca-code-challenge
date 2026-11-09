"""The JSON API. Function views, like the pages (ADR 0026)."""

import logging
from typing import TYPE_CHECKING

from brandreviews_authz import is_claims, scopes
from brandreviews_authz.drf import require_scopes
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from django.views.decorators.http import conditional_page
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import ListSerializer

from catalog.api.query import BrandListQuerySerializer, brand_cards
from catalog.api.serializers import BrandCardSerializer, BrandEditSerializer
from catalog.models import Brand

if TYPE_CHECKING:
    from rest_framework.request import Request

logger = logging.getLogger(__name__)


class BrandPagination(PageNumberPagination):
    """DRF's page-number envelope, with the page size already validated.

    page_size_query_param stays unset: BrandListQuerySerializer is the only
    parser of ?page_size, so a value it rejects can't be clamped or
    replaced here. ?page stays DRF's: a page past the end is a 404.
    """

    def __init__(self, page_size: int) -> None:
        self.page_size = page_size


# Browsers and proxies may store the listing but must revalidate every time;
# the ETag turns an unchanged page into a 304. That saves bandwidth, not
# database work. No server-side cache: Django's cache middleware had seven
# data-exposure CVEs in 2026 (ADR 0027).
@conditional_page
@cache_control(public=True, no_cache=True)
@api_view(["GET"])
# Public, and never reads the Authorization header: an expired token must not
# turn the public listing into a 401.
@authentication_classes([])
@permission_classes([AllowAny])
def brand_list(request: Request) -> Response:
    params = BrandListQuerySerializer.from_query_params(request.query_params)
    params.is_valid(raise_exception=True)
    query = params.to_query()
    brands = brand_cards(query)
    paginator = BrandPagination(query.page_size)
    # None only when a paginator has no page size; this one always has one.
    page = paginator.paginate_queryset(brands, request) or []
    cards = ListSerializer[list[Brand]](page, child=BrandCardSerializer())
    return paginator.get_paginated_response(cards.data)


@api_view(["PATCH"])
# Authentication is the default (catalog.api.authentication); this names the
# scope. Credentials are checked before the brand is looked up, so the
# endpoint can't be used to probe slugs.
@permission_classes([require_scopes(scopes.BRANDS_WRITE)])
def brand_update(request: Request, slug: str) -> Response:
    """Change a published brand's short description. Editors only (ADR 0034).

    Last write wins: no If-Match. The log line records who wrote what when,
    so an overwritten edit can be traced.
    """
    claims = request.auth
    if not is_claims(claims):
        # require_scopes only lets claims through; fail closed, not with an
        # assert that `python -O` would strip.
        raise PermissionDenied
    brand = get_object_or_404(Brand.objects.published(), slug=slug)
    body = BrandEditSerializer(data=request.data)
    body.is_valid(raise_exception=True)
    brand.short_description = body.validated_data["short_description"]
    # updated_at is auto_now; it's only written when listed.
    brand.save(update_fields=["short_description", "updated_at"])
    logger.info("brand edited slug=%s sub=%s jti=%s", brand.slug, claims.subject, claims.token_id)
    return Response({"slug": brand.slug, "short_description": brand.short_description})
