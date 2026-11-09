from django.urls import path

from catalog.api import views

app_name = "api"

urlpatterns = [
    path("brands/", views.brand_list, name="brand-list"),
    path("brands/<slug:slug>/", views.brand_update, name="brand-update"),
]
