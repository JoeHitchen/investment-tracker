from typing import Any

from django import template

from invest.templatetags.invest_tags import GBP


register = template.Library()


@register.filter
def lookup(dictionary: dict[str, Any], key: str) -> Any:
    return dictionary.get(key)


@register.filter(name = 'float')
def to_float(value: str) -> float:
    return float(value)


@register.filter
def GBP_with_blank(value: float) -> str:
    if not value:
        return '-'
    return GBP(value)
