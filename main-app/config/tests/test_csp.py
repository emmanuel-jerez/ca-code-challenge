import pytest
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, override_settings

from config.csp import ContentSecurityPolicyMiddleware

POLICY = "default-src 'self'; script-src 'self'; style-src 'self'"


def respond(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


@pytest.mark.parametrize(
    ("report_only", "header", "absent"),
    [
        (True, "Content-Security-Policy-Report-Only", "Content-Security-Policy"),
        (False, "Content-Security-Policy", "Content-Security-Policy-Report-Only"),
    ],
)
def test_policy_is_sent_in_the_configured_mode(report_only: bool, header: str, absent: str) -> None:
    with override_settings(CSP_POLICY=POLICY, CSP_REPORT_ONLY=report_only):
        response = ContentSecurityPolicyMiddleware(respond)(RequestFactory().get("/"))

    assert response[header] == POLICY
    assert absent not in response
