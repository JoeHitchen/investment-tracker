from datetime import datetime
from typing import TypedDict
import logging

import requests
from bs4 import BeautifulSoup
from django.db import IntegrityError
from django.utils import timezone
from typing_extensions import Unpack
from celery import Celery

from core import tasks
from sipp import models as sipp
from sipp.utils import exists


logger = logging.getLogger('sipp-tracker')


class Kwargs(TypedDict):
    pass


def get_latest_fund_price(fund: sipp.Fund) -> sipp.PricePoint:

    response = requests.get(fund.url)
    if not response.ok:
        response.raise_for_status()

    fund_page_soup = BeautifulSoup(response.text, 'html.parser')
    price_line_soup = fund_page_soup.select_one('span.price-divide')
    assert price_line_soup
    price_text = price_line_soup.text.strip()
    price_value = int(price_text[:-1].replace('.', '').replace(',', ''))

    price_date_soup = fund_page_soup.select_one('div.price-unavailable')
    assert price_date_soup
    price_date_text = price_date_soup.text.strip()
    price_date = datetime.strptime(price_date_text[13:], '%d %B %Y').date()

    try:
        return sipp.PricePoint.objects.create(
            fund=fund,
            date=price_date,
            hundredths=price_value,
        )
    except IntegrityError:
        return exists(fund.price_points.last())


@tasks.task
def current_time() -> str:
    logger.info(timezone.now().isoformat())
    return timezone.now().isoformat()


@tasks.on_after_finalize.connect
def setup_periodic_tasks(sender: Celery, **_: Unpack[Kwargs]) -> None:
    sender.add_periodic_task(60, current_time.s())

