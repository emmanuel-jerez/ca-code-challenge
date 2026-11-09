"""Users, and the scopes each role (a Django Group) grants.

The main app never sees these rows. It learns only `external_id`, as the
token's `sub`, and the scopes in the token (ADR 0033).
"""

import uuid

from django.contrib.auth.models import AbstractUser, Group
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower


class UsernameValidator(RegexValidator):
    """Django's username characters minus `@`.

    The login backend reads an identifier with `@` as an email address, so
    no username may contain one (ADR 0033).
    """

    regex = r"^[\w.+-]+\Z"
    message = "Enter a valid username: letters, digits and . + - _ only."
    flags = 0


class User(AbstractUser):
    username = models.CharField(
        "username",
        max_length=150,
        unique=True,
        help_text="Required. 150 characters or fewer. Letters, digits and . + - _ only.",
        validators=[UsernameValidator()],
        error_messages={"unique": "A user with that username already exists."},
    )
    # The token's `sub` and the only user id the main app stores. Random
    # (v4): v7 would reveal when each account was created (RFC 9562).
    external_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    # The re-import key; empty for users created here.
    wp_user_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True)

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"
        constraints = [
            # WordPress logins and emails are case-insensitive; so are ours.
            models.UniqueConstraint(Lower("username"), name="user_username_ci_unique"),
            models.UniqueConstraint(
                Lower("email"),
                condition=~models.Q(email=""),
                name="user_email_ci_unique",
            ),
        ]


scope_name_validator = RegexValidator(
    r"^[a-z]+:[a-z]+\Z", "A scope is resource:action in lowercase, e.g. brands:write."
)


class Scope(models.Model):
    """A permission as it appears in the token's `scope` claim.

    The main app checks scopes, never role names, so roles can be split or
    renamed here without a code change there.
    """

    name = models.CharField(max_length=64, unique=True, validators=[scope_name_validator])
    groups = models.ManyToManyField(Group, related_name="scopes", blank=True)

    def __str__(self) -> str:
        return self.name
