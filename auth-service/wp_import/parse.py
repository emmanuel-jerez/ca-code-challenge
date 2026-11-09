"""Turn raw WordPress users into checked import rows (ADR 0024)."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from accounts.models import UsernameValidator
from wp_import.errors import InvalidValue

if TYPE_CHECKING:
    from wp_import.source import RawWpUser

# WordPress role → auth role. The administrator becomes an editor, not a
# superuser: nothing here needs a superuser. Unmapped roles get no role.
ROLE_MAP = {"administrator": "editor", "subscriber": "reader"}

# PHP's serialize() of an array of string keys to booleans, the only shape
# wp_capabilities takes. Parsed here rather than with a PHP-unserialize
# package: one key, a strict grammar, and no object instantiation to worry about.
_ARRAY = re.compile(r"a:(\d+):\{(.*)\}", re.DOTALL)
_ENTRY = re.compile(r's:(\d+):"([^"]*)";b:([01]);')


def parse_wp_roles(wp_id: int, capabilities: str | None) -> frozenset[str]:
    """The WordPress roles a wp_capabilities value marks true."""
    if capabilities is None:
        return frozenset()
    array = _ARRAY.fullmatch(capabilities)
    if array is None:
        raise InvalidValue(wp_id, "wp_capabilities is not a serialized array")
    body = array.group(2)
    roles: set[str] = set()
    count = 0
    position = 0
    while position < len(body):
        entry = _ENTRY.match(body, position)
        if entry is None:
            raise InvalidValue(wp_id, "wp_capabilities has an entry that isn't string → bool")
        declared, name, flag = entry.groups()
        # PHP counts bytes, not characters.
        if int(declared) != len(name.encode()):
            raise InvalidValue(wp_id, f"wp_capabilities declares the wrong length for {name!r}")
        if flag == "1":
            roles.add(name)
        count += 1
        position = entry.end()
    if count != int(array.group(1)):
        raise InvalidValue(wp_id, "wp_capabilities declares the wrong number of entries")
    return frozenset(roles)


@dataclass(frozen=True, slots=True)
class WpUser:
    wp_user_id: int
    username: str
    email: str
    # Auth roles (Group names) the WordPress roles map to.
    roles: frozenset[str]
    unmapped_roles: tuple[str, ...]


_validate_username = UsernameValidator()


def parse_user(raw: RawWpUser) -> WpUser:
    try:
        _validate_username(raw.login)
    except ValidationError:
        raise InvalidValue(
            raw.id, f"username {raw.login!r} has characters we don't allow"
        ) from None
    try:
        validate_email(raw.email)
    except ValidationError:
        raise InvalidValue(raw.id, f"email {raw.email!r} is not valid") from None
    wp_roles = parse_wp_roles(raw.id, raw.capabilities)
    return WpUser(
        wp_user_id=raw.id,
        username=raw.login,
        email=raw.email,
        roles=frozenset(ROLE_MAP[role] for role in wp_roles if role in ROLE_MAP),
        unmapped_roles=tuple(sorted(role for role in wp_roles if role not in ROLE_MAP)),
    )
