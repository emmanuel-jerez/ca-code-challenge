"""Role changes and the reviewer map, through manage.py (ADR 0033)."""

import json
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from django.core.management import CommandError, call_command

from accounts.roles import scopes_for

if TYPE_CHECKING:
    from collections.abc import Callable

    from accounts.models import User

pytestmark = pytest.mark.django_db


def test_granting_editor_adds_write_to_the_next_token(make_user: Callable[..., User]) -> None:
    user = make_user("reader", username="sarah_k")
    out = StringIO()

    call_command("grant_role", "SARAH_K", "editor", stdout=out)

    assert scopes_for(user) == ["brands:read", "brands:write"]
    assert "within 10 minutes" in out.getvalue()


def test_revoking_editor_removes_write_from_the_next_token(
    make_user: Callable[..., User],
) -> None:
    user = make_user("reader", "editor")

    call_command("revoke_role", user.username, "editor", stdout=StringIO())

    assert scopes_for(user) == ["brands:read"]


@pytest.mark.parametrize(
    ("username", "role", "message"),
    [("nobody", "editor", "No user"), ("sarah_k", "admin", "No role")],
)
def test_role_commands_refuse_unknown_users_and_roles(
    make_user: Callable[..., User], username: str, role: str, message: str
) -> None:
    make_user(username="sarah_k")

    with pytest.raises(CommandError, match=message):
        call_command("grant_role", username, role)


def test_the_user_map_links_wordpress_ids_to_external_ids_and_nothing_else(
    make_user: Callable[..., User],
) -> None:
    imported = make_user("reader", wp_user_id=2)
    make_user("editor")  # created here, so it has no WordPress id
    out = StringIO()

    call_command("export_user_map", stdout=out)

    assert json.loads(out.getvalue()) == {
        "version": 1,
        "users": [{"wp_user_id": 2, "external_id": str(imported.external_id)}],
    }
