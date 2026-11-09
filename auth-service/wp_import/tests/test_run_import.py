"""The user import against a fake WordPress (ADR 0024)."""

import pytest
from django.contrib.auth.models import Group

from accounts.models import User
from accounts.roles import scopes_for
from wp_import.errors import WpImportError
from wp_import.service import run_user_import
from wp_import.tests.fakes import FakeWordPress

pytestmark = pytest.mark.django_db


def roles(user: User) -> list[str]:
    return sorted(user.groups.values_list("name", flat=True))


def test_imports_users_with_no_usable_password_and_mapped_roles() -> None:
    wp = FakeWordPress()
    wp.add_user(1, "admin", roles=("administrator",))
    wp.add_user(2, "sarah_k")

    report = run_user_import(wp)

    admin = User.objects.get(wp_user_id=1)
    sarah = User.objects.get(wp_user_id=2)
    assert (report.created, report.updated, report.unchanged) == (2, 0, 0)
    assert not admin.has_usable_password()
    assert not admin.is_superuser
    assert roles(admin) == ["editor"]
    assert roles(sarah) == ["reader"]
    assert sarah.email == "sarah_k@example.com"


def test_a_rerun_keeps_passwords_and_roles_changed_here() -> None:
    wp = FakeWordPress()
    wp.add_user(2, "sarah_k")
    run_user_import(wp)
    sarah = User.objects.get(wp_user_id=2)
    sarah.set_password("a password set after cutover")
    sarah.save()
    sarah.groups.add(Group.objects.get(name="editor"))

    report = run_user_import(wp)

    sarah.refresh_from_db()
    assert (report.created, report.updated, report.unchanged) == (0, 0, 1)
    assert sarah.check_password("a password set after cutover")
    assert scopes_for(sarah) == ["brands:read", "brands:write"]


def test_a_rerun_follows_a_login_or_email_changed_in_wordpress() -> None:
    wp = FakeWordPress()
    wp.add_user(2, "sarah_k")
    run_user_import(wp)
    external_id = User.objects.get(wp_user_id=2).external_id
    wp.people.clear()
    wp.add_user(2, "sarah_kim", email="sarah@example.org")

    report = run_user_import(wp)

    sarah = User.objects.get(wp_user_id=2)
    assert report.updated == 1
    assert (sarah.username, sarah.email) == ("sarah_kim", "sarah@example.org")
    assert sarah.external_id == external_id


def test_an_unmapped_role_imports_the_user_with_no_role_and_a_warning() -> None:
    wp = FakeWordPress()
    wp.add_user(5, "pat", roles=("author",))

    report = run_user_import(wp)

    assert roles(User.objects.get(wp_user_id=5)) == []
    assert report.warnings == ["user 5: WordPress role 'author' has no mapping; given no role"]


@pytest.mark.parametrize(
    ("login", "email", "problem"),
    [
        ("pat@home", "pat@example.com", "username"),
        ("pat", "not an email", "email"),
    ],
)
def test_a_bad_row_stops_the_import_before_anything_is_written(
    login: str, email: str, problem: str
) -> None:
    wp = FakeWordPress()
    wp.add_user(2, "sarah_k")
    wp.add_user(3, login, email=email)

    with pytest.raises(WpImportError, match=f"user 3: .*{problem}"):
        run_user_import(wp)

    assert not User.objects.exists()


def test_a_name_already_taken_here_stops_the_import() -> None:
    User.objects.create_user(username="Sarah_K")
    wp = FakeWordPress()
    wp.add_user(2, "sarah_k")

    with pytest.raises(WpImportError, match="already"):
        run_user_import(wp)

    assert User.objects.count() == 1


def test_a_dry_run_reports_but_writes_nothing() -> None:
    wp = FakeWordPress()
    wp.add_user(2, "sarah_k")

    report = run_user_import(wp, dry_run=True)

    assert report.created == 1
    assert not User.objects.exists()
