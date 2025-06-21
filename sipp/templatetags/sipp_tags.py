from django import template
from django.utils.html import format_html


register = template.Library()


@register.filter
def GBP(value: float) -> str:
    sign = '&minus;' if value < 0 else ''
    return format_html(f'<span class="nobr">{sign}£{abs(value):,.2f}</span>')

