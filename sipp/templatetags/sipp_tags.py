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


def _next_working_day(this_date: date) -> date:
    """Returns the next working day after the given date."""
    day_to_add = {
        4: 3,  # Friday
        5: 2,  # Saturday
        6: 1,  # Sunday
    }.get(this_date.weekday(), 1)
    return this_date + timedelta(days=day_to_add)


@register.filter
def GBP(value: float) -> str:
    sign = '&minus;' if value < 0 else ''
    return mark_safe(f'<span class="no-wrap">{sign}£{abs(value):,.2f}</span>')


@register.filter
def percent(value: float) -> str:
    sign = '&minus;' if value < 0 else ''
    return mark_safe(f'<span class="no-wrap">{sign}{abs(value):,.1f}%</span>')


@register.filter
def is_todays_price(price_date: date) -> str:
    if not price_date:
        return ''

    deadline = timezone.make_aware(datetime.combine(_next_working_day(price_date), time(17, 00)))
    if timezone.now() < deadline:
        return ''

    return format_html(
        '&nbsp;<span data-toggle="tooltip" title="Price last updated {} ago">🕔</span>',
        timesince(timezone.make_aware(datetime.combine(price_date, time(17, 00)))),
    )


@register.filter
def is_green_fund(green: bool) -> str:
    return '🌳' if green else ''


@register.filter
def format_timeseries(data: list[tuple[date, float]]) -> list[TimeSeriesPoint]:
    return [
        {'x': day.isoformat(), 'y': round(value, 2)}
        for day, value in data if day.weekday() < 5
    ]

