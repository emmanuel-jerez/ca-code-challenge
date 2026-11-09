"""Turning WordPress HTML into what the site stores and renders.

Sanitized once at import with nh3 and an explicit allow-list (ADRs 0004, 0026).
Never allow `style`, `svg`, `math` or `animate*`: nh3 0.3.7 bundles an ammonia
with open advisories that need them (ADR 0018).
"""

import html
import re

import nh3

CLEANER = nh3.Cleaner(
    tags={
        "p",
        "br",
        "strong",
        "em",
        "b",
        "i",
        "ul",
        "ol",
        "li",
        "blockquote",
        "a",
        "h2",
        "h3",
        "h4",
        "code",
        "pre",
    },
    attributes={"a": {"href", "title"}},
    url_schemes={"http", "https", "mailto"},
    link_rel="nofollow noopener noreferrer ugc",
)

_BLOCK_TAG = re.compile(r"<(p|div|ul|ol|blockquote|h[1-6]|pre|table)[\s>]", re.IGNORECASE)
_BLANK_LINES = re.compile(r"\n\s*\n")
# Tags that end a run of text. Stripping them without a space would glue
# "agents.</p><p>Acme" into "agents.Acme".
_TEXT_BREAK = re.compile(
    r"<(/?(?:p|div|br|li|ul|ol|blockquote|h[1-6]|pre|table|tr|td|th)\b)", re.IGNORECASE
)
_SHORTCODE = re.compile(r"\[/?[a-z][a-z0-9_-]*(\s[^\]]*)?\]", re.IGNORECASE)


def to_safe_html(source: str) -> str:
    """Sanitized HTML for templates. The only HTML the site ever renders."""
    return CLEANER.clean(autop(source))


def autop(source: str) -> str:
    """A minimal stand-in for WordPress's wpautop.

    Bodies with block tags pass through unchanged (every body in the dump).
    Plain text gets a <p> per blank-line-separated chunk and <br> for single
    newlines, which is what wpautop does for that case.
    """
    text = source.replace("\r\n", "\n").strip()
    if not text or _BLOCK_TAG.search(text):
        return text
    chunks = (chunk.strip() for chunk in _BLANK_LINES.split(text))
    return "".join(f"<p>{chunk.replace('\n', '<br>')}</p>" for chunk in chunks if chunk)


def to_plain_text(source: str) -> str:
    """Text with tags removed and entities decoded. Autoescaped on output."""
    spaced = _TEXT_BREAK.sub(r" <\1", source)
    return " ".join(html.unescape(nh3.clean(spaced, tags=set())).split())


def first_words(text: str, count: int, max_length: int) -> str:
    """The theme's wp_trim_words: the first `count` words, with an ellipsis if cut."""
    words = text.split()
    excerpt = " ".join(words[:count])
    if len(words) > count:
        excerpt += "…"
    if len(excerpt) > max_length:
        excerpt = excerpt[: max_length - 1].rstrip() + "…"
    return excerpt


def has_shortcode(source: str) -> bool:
    """WordPress shortcodes render as literal text here; the import warns about them."""
    return _SHORTCODE.search(source) is not None
