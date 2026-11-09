"""manage.py export_user_map > user-map.json: WordPress id → external id.

The main app's import reads this to link each Reviewer to its auth account
(ADR 0020). It carries no usernames, emails or hashes.
"""

import json
from typing import Any

from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Print the wp_user_id → external_id map for imported users, as JSON."

    def handle(self, *args: object, **options: Any) -> None:  # noqa: ANN401 - Django's signature
        rows = (
            User.objects.filter(wp_user_id__isnull=False)
            .order_by("wp_user_id")
            .values_list("wp_user_id", "external_id")
        )
        document = {
            "version": 1,
            "users": [
                {"wp_user_id": wp_id, "external_id": str(external_id)}
                for wp_id, external_id in rows
            ],
        }
        self.stdout.write(json.dumps(document, indent=2))
