from datetime import datetime
from typing import TypedDict, Unpack
from enum import Enum
import logging
import random
import time

import requests
from bs4 import BeautifulSoup
from celery import Celery
from celery.schedules import crontab

from core import tasks
from invest import models as invest
from invest.utils import Kwargs


logger = logging.getLogger('invest')


class RefreshStatus(Enum):
    CREATED = 'Created'
    UPDATED = 'Updated'
    NO_CHANGE = 'No Change'


class RefreshFundPriceResult(TypedDict):
    fund: str
    price: float
    status: str


def refresh_fund_price(
    fund: invest.Fund,
) -> tuple[invest.PricePoint, RefreshStatus]:

    logger.info('{} ({}) - Refreshing price...'.format(
        fund.short_name,
        fund.tag,
    ))

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

    logger.info('{} ({}) - Refreshed price: {}p ({})'.format(
        fund.short_name,
        fund.tag,
        price_value / 100,
        price_date,
    ))

    price_point, created = fund.price_points.get_or_create(
        date=price_date,
        defaults={'hundredths': price_value},
    )
    status = RefreshStatus.CREATED if created else RefreshStatus.NO_CHANGE
    if not created and price_point.hundredths != price_value:
        status = RefreshStatus.UPDATED
        price_point.hundredths = price_value
        price_point.save()

    logger.info('{} ({}) - {}'.format(
        fund.short_name,
        fund.tag,
        status.value,
    ))
    return price_point, status


@tasks.task
def refresh_fund_price_async(fund_id: int) -> RefreshFundPriceResult:
    price_point, status = refresh_fund_price(invest.Fund.objects.get(id=fund_id))
    return {
        'fund': f'{price_point.fund.short_name} ({price_point.fund.tag})',
        'price': price_point.pence,
        'status': status.value,
    }


@tasks.task
def refresh_fund_prices_async() -> None:
    time.sleep(random.randint(0, 60))
    for fund in invest.Fund.objects.filter(monitor_price = True):
        refresh_fund_price_async.delay(fund.id)


@tasks.on_after_finalize.connect
def setup_periodic_tasks(sender: Celery, **_: Unpack[Kwargs]) -> None:
    sender.add_periodic_task(
        crontab(hour='7,13,17,18,20,23', minute=35),
        refresh_fund_prices_async.s(),
    )

