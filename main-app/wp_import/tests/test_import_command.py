"""The import command against the WordPress MariaDB from docker compose.

Skipped when that database isn't reachable. Run `make up` and
`make wp-import-user` first; the password comes from WP_IMPORT_DB_PASSWORD
(the local default is `wp_import`).
"""

import os
from decimal import Decimal
from io import StringIO

import pymysql
import pytest
from django.core.management import call_command

from catalog.models import Brand
from wp_import.source import WpDbSettings

pytestmark = [pytest.mark.wordpress, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def wordpress_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "WP_IMPORT_DB_PASSWORD", os.environ.get("WP_IMPORT_DB_PASSWORD", "wp_import")
    )
    settings = WpDbSettings.from_env()
    try:
        pymysql.connect(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password,
            database=settings.database,
            connect_timeout=2,
        ).close()
    except pymysql.err.OperationalError as error:
        pytest.skip(f"WordPress MariaDB not reachable: {error}")


def test_imports_the_seeded_site_and_a_rerun_writes_nothing() -> None:
    first, second = StringIO(), StringIO()

    call_command("import_wp", stdout=first)
    call_command("import_wp", stdout=second)

    assert "reviews: 60 created" in first.getvalue()
    assert "brands: 0 created, 0 updated, 5 unchanged" in second.getvalue()
    assert "reviews: 0 created, 0 updated, 60 unchanged" in second.getvalue()
    # ADR 0019: computed means, highest first; WordPress's stored values differ.
    ratings = list(
        Brand.objects.order_by("-average_rating").values_list(
            "slug", "average_rating", "legacy_average_rating"
        )
    )
    assert ratings == [
        ("acme-insurance", Decimal("3.92"), Decimal("4.2")),
        ("primepath-bank", Decimal("3.83"), Decimal("4.0")),
        ("urbanretail-co", Decimal("3.67"), Decimal("4.4")),
        ("swiftstream-internet", Decimal("3.50"), Decimal("3.5")),
        ("homeshield-pro", Decimal("3.08"), Decimal("3.9")),
    ]
