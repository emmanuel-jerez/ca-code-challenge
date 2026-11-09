"""Loads a Vite build entry on a Django page (ADR 0031).

`pnpm build` writes a manifest mapping each source entry to its hashed
output. This tag reads it and emits the entry's stylesheets, then its module
script, both through `static()`, which is the order Vite's backend guide
gives. A ~40-line tag instead of django-vite, which doesn't declare Django
5.2 or Python 3.14 (docs/research/pillar-3-brandlist-component.md §9).
"""

import json
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, TypeIs

from django import template
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static
from django.utils.html import format_html, format_html_join

if TYPE_CHECKING:
    from pathlib import Path

    from django.utils.safestring import SafeString

register = template.Library()

# Where Django serves the Vite build (STATICFILES_DIRS) and Vite's `base`.
STATIC_PREFIX = "frontend/"


@dataclass(frozen=True)
class Entry:
    file: str
    css: tuple[str, ...]


def _is_str_list(value: object) -> TypeIs[list[str]]:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


@cache
def _read_entry(manifest_path: Path, name: str) -> Entry:
    """Read once per process: the build only changes when the image does."""
    try:
        manifest: object = json.loads(manifest_path.read_text())
    except FileNotFoundError:
        raise ImproperlyConfigured(
            f"No Vite manifest at {manifest_path}. Run `pnpm build` in frontend/."
        ) from None
    entry = manifest.get(name) if isinstance(manifest, dict) else None
    if not isinstance(entry, dict):
        raise ImproperlyConfigured(f"{manifest_path} has no entry {name!r}.")
    file = entry.get("file")
    css = entry.get("css", [])
    if not isinstance(file, str) or not _is_str_list(css):
        raise ImproperlyConfigured(f"{manifest_path} has a malformed entry {name!r}.")
    return Entry(file=file, css=tuple(css))


@register.simple_tag
def vite_entry(name: str) -> SafeString:
    entry = _read_entry(settings.VITE_MANIFEST_PATH, name)
    stylesheets = format_html_join(
        "",
        '<link rel="stylesheet" href="{}">',
        ((static(STATIC_PREFIX + css),) for css in entry.css),
    )
    script = format_html(
        '<script type="module" src="{}"></script>', static(STATIC_PREFIX + entry.file)
    )
    return stylesheets + script
