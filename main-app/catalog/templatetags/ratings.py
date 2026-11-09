"""Star ratings, drawn like the WordPress theme's cr_stars()."""

import math
from decimal import ROUND_HALF_UP, Decimal

from django import template

register = template.Library()


@register.inclusion_tag("catalog/_stars.html")
def stars(rating: Decimal | int | None, *, show_value: bool = True) -> dict[str, object]:
    """Full stars are the rating rounded down, as in the theme."""
    if rating is None:
        return {"rated": False}
    value = min(max(Decimal(rating), Decimal(0)), Decimal(5))
    full = math.floor(value)
    return {
        "rated": True,
        # Half up, like PHP's number_format() in the theme.
        "value": value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
        "full": range(full),
        "empty": range(5 - full),
        "show_value": show_value,
    }
