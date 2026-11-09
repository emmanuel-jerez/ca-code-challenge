"""Seed the two roles and the scopes each grants (ADR 0033).

A data migration, not post_migrate, so a fresh database has the roles before
anything else runs. Historical models only, as data migrations require.
`brands:read` guards nothing yet (the listing is public); it gives readers a
meaningful token and somewhere to grow.
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

ROLES = {
    "reader": ["brands:read"],
    "editor": ["brands:read", "brands:write"],
}


def seed(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Group = apps.get_model("auth", "Group")
    Scope = apps.get_model("accounts", "Scope")
    for role, scope_names in ROLES.items():
        group, _ = Group.objects.get_or_create(name=role)
        for name in scope_names:
            scope, _ = Scope.objects.get_or_create(name=name)
            scope.groups.add(group)


def unseed(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    apps.get_model("accounts", "Scope").objects.filter(
        name__in={name for names in ROLES.values() for name in names}
    ).delete()
    apps.get_model("auth", "Group").objects.filter(name__in=ROLES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
