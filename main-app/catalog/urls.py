"""Same paths as WordPress's permalinks (`/%postname%/` with CPT rewrite slugs).

APPEND_SLASH (on by default) sends /brand/x to /brand/x/ with a 301, as
WordPress does.
"""

from django.urls import path

from catalog import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("brand/", views.brand_list, name="brand-list"),
    path("brand/<slug:slug>/", views.brand_detail, name="brand-detail"),
    path("review/<slug:slug>/", views.review_detail, name="review-detail"),
]
