"""The core must import and run without Django (CHALLENGE.md Pillar 6)."""

import subprocess
import sys


def test_importing_the_core_loads_neither_django_nor_drf() -> None:
    # A fresh interpreter, isolated (-I), since this test session has
    # imported Django already for the adapter's tests.
    code = (
        "import sys, brandreviews_authz, brandreviews_authz.scopes;"
        "loaded = {'django', 'rest_framework'} & sys.modules.keys();"
        "assert not loaded, loaded"
    )

    result = subprocess.run(  # noqa: S603 - fixed arguments, our own interpreter
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
