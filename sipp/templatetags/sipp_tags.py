from datetime import datetime, date, time, timedelta
from typing import TypedDict

from django import template
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.timesince import timesince


class TimeSeriesPoint(TypedDict):
    x: str
    y: float


register = template.Library()


@register.filter
def GBP(value: float) -> str:
    sign = '&minus;' if value < 0 else ''
    return mark_safe(f'<span class="nobr">{sign}£{abs(value):,.2f}</span>')


@register.filter
def percent(value: float) -> str:
    sign = '&minus;' if value < 0 else ''
    return mark_safe(f'<span class="nobr">{sign}{abs(value):,.1f}%</span>')


@register.filter
def is_todays_price(price_date: date) -> str:

    time_shift = timedelta(
        days = max(timezone.now().isoweekday() - 5, 0),
        hours = 17,
    )
    if price_date >= (timezone.now() - time_shift).date():
        return ''

    return format_html(
        '&nbsp;<span data-toggle="tooltip" title="Price last updated {} ago">🕔</span>',
        timesince(timezone.make_aware(datetime.combine(price_date, time(17, 00)))),
    )


@register.filter
def format_timeseries(data: list[tuple[date, float]]) -> list[TimeSeriesPoint]:
    return [
        {'x': day.isoformat(), 'y': round(value, 2)}
        for day, value in data if day.weekday() < 5
    ]

