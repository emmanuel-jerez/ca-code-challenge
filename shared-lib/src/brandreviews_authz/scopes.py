"""Scope names: the auth service grants them, the main app requires them.

A typo here is an import error, not a silent 403. Which role grants which
scope is the auth service's data and stays there (ADR 0033): roles can
change without a library release, scope names can't.
"""

from typing import Final

BRANDS_READ: Final = "brands:read"
BRANDS_WRITE: Final = "brands:write"

ALL: Final = frozenset({BRANDS_READ, BRANDS_WRITE})
