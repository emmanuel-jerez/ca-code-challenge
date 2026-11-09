from django.urls import path

from accounts import views

urlpatterns = [
    path("api/token/", views.token, name="token"),
    # A convention, not an IANA-registered path; the main app configures the URL.
    path(".well-known/jwks.json", views.jwks, name="jwks"),
    path("healthz", views.healthz, name="healthz"),
]
