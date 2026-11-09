"""Log in by username or email, case-insensitively, as WordPress 6.9 allows."""

from typing import TYPE_CHECKING

from django.contrib.auth.backends import ModelBackend

from accounts.models import User

if TYPE_CHECKING:
    from django.http import HttpRequest


class UsernameOrEmailBackend(ModelBackend):
    """ModelBackend with one change: how the user is looked up.

    An identifier with `@` is an email address; usernames can't contain `@`
    (accounts.models.UsernameValidator), so the two never collide. The
    database's case-insensitive unique constraints make each lookup match at
    most one row.
    """

    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: object,
    ) -> User | None:
        if username is None or password is None:
            return None
        lookup = {"email__iexact" if "@" in username else "username__iexact": username}
        try:
            user = User._default_manager.get(**lookup)
        except User.DoesNotExist:
            # Hash anyway, as ModelBackend does, so an unknown name takes
            # about as long as a wrong password.
            User().set_password(password)
            return None
        # Checked after the hash, so inactive users fail at the same speed.
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
