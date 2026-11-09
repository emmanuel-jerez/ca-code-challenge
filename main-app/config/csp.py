"""Content Security Policy header (ADR 0017).

Django 5.2 has no built-in CSP, and django-csp doesn't declare Python 3.14, so
this small middleware sets one header from settings. No nonces: templates carry
no inline scripts or styles.
"""

from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        header = (
            "Content-Security-Policy-Report-Only"
            if settings.CSP_REPORT_ONLY
            else "Content-Security-Policy"
        )
        response[header] = settings.CSP_POLICY
        return response
