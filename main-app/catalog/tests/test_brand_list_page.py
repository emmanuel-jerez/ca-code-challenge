"""The /brand/ page, WordPress's brand archive URL, which mounts <BrandList />."""

import json
from typing import TYPE_CHECKING

import pytest
from django.core.exceptions import ImproperlyConfigured

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from django.test import Client
    from pytest_django import DjangoAssertNumQueries
    from pytest_django.fixtures import Settings

    from catalog.models import Industry

ENTRY = "src/brand-list/main.tsx"


@pytest.fixture
def vite_manifest(tmp_path: Path, settings: Settings) -> Path:
    """A Vite manifest like `pnpm build` writes, with one entry and one stylesheet."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                ENTRY: {
                    "file": "assets/brandList-abc123.js",
                    "src": ENTRY,
                    "isEntry": True,
                    "css": ["assets/brandList-def456.css"],
                }
            }
        )
    )
    settings.VITE_MANIFEST_PATH = manifest
    return manifest


@pytest.mark.django_db
@pytest.mark.usefixtures("vite_manifest")
def test_brand_page_mounts_the_component_with_the_api_url_and_industries(
    client: Client,
    make_industry: Callable[..., Industry],
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    make_industry(name="Telecom", slug="telecom")
    make_industry(name="Finance", slug="finance")

    with django_assert_num_queries(1):
        response = client.get("/brand/")

    assert response.status_code == 200
    html = response.content.decode()
    assert '<div id="brand-list" data-api-url="/api/brands/">' in html
    # json_script, as the mount code reads it; sorted by name for the filter.
    assert (
        '<script id="brand-list-industries" type="application/json">'
        '[{"slug": "finance", "name": "Finance"}, {"slug": "telecom", "name": "Telecom"}]'
        "</script>"
    ) in html


@pytest.mark.django_db
@pytest.mark.usefixtures("vite_manifest")
def test_brand_page_loads_the_build_entry_and_its_stylesheets_from_static(
    client: Client,
) -> None:
    html = client.get("/brand/").content.decode()

    assert '<link rel="stylesheet" href="/static/frontend/assets/brandList-def456.css">' in html
    assert '<script type="module" src="/static/frontend/assets/brandList-abc123.js">' in html


@pytest.mark.django_db
@pytest.mark.usefixtures("vite_manifest")
def test_brand_page_is_the_current_page_in_the_navigation(client: Client) -> None:
    html = client.get("/brand/").content.decode()

    assert '<a class="c-site-nav__link" href="/brand/" aria-current="page">Brands</a>' in html


@pytest.mark.django_db
def test_brand_page_fails_loudly_without_a_frontend_build(
    client: Client, tmp_path: Path, settings: Settings
) -> None:
    settings.VITE_MANIFEST_PATH = tmp_path / "missing.json"

    with pytest.raises(ImproperlyConfigured, match="pnpm build"):
        client.get("/brand/")
