"""The user import command against the WordPress MariaDB from docker compose.

Skipped when that database isn't reachable. Run `make up` and
`make wp-import-user` first; the password comes from WP_IMPORT_DB_PASSWORD
(the local default is `wp_auth_import`).
"""

import os
from io import StringIO

import pymysql
import pytest
from django.core.management import call_command

from accounts.models import User
from wp_import.source import WpDbSettings

pytestmark = [pytest.mark.wordpress, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def wordpress_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "WP_IMPORT_DB_PASSWORD", os.environ.get("WP_IMPORT_DB_PASSWORD", "wp_auth_import")
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


def test_imports_the_seeded_users_and_a_rerun_writes_nothing() -> None:
    first, second = StringIO(), StringIO()

    call_command("import_wp_users", stdout=first)
    call_command("import_wp_users", stdout=second)

    assert "users: 9 created, 0 updated, 0 unchanged" in first.getvalue()
    assert "users: 0 created, 0 updated, 9 unchanged" in second.getvalue()
    # ADR 0024: one administrator → editor, eight subscribers → reader.
    roles = sorted(User.objects.values_list("groups__name", flat=True))
    assert roles == ["editor"] + ["reader"] * 8
    assert not any(user.has_usable_password() for user in User.objects.all())
