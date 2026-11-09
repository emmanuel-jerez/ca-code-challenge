"""wp_capabilities: a PHP-serialized array, parsed strictly without a PHP library."""

import pytest

from wp_import.errors import InvalidValue
from wp_import.parse import parse_wp_roles


def test_reads_the_roles_wordpress_marks_true() -> None:
    value = 'a:3:{s:13:"administrator";b:1;s:10:"subscriber";b:1;s:6:"author";b:0;}'

    assert parse_wp_roles(1, value) == frozenset({"administrator", "subscriber"})


def test_a_user_without_capabilities_has_no_roles() -> None:
    assert parse_wp_roles(1, None) == frozenset()
    assert parse_wp_roles(1, "a:0:{}") == frozenset()


@pytest.mark.parametrize(
    "value",
    [
        'a:1:{s:12:"subscriber";b:1;}',  # declared length is wrong
        'a:2:{s:10:"subscriber";b:1;}',  # declared count is wrong
        'a:1:{s:10:"subscriber";i:1;}',  # not a boolean
        'O:8:"stdClass":0:{}',  # an object, not an array
        "subscriber",
    ],
)
def test_anything_else_stops_the_import(value: str) -> None:
    with pytest.raises(InvalidValue, match="user 7"):
        parse_wp_roles(7, value)
