from datetime import datetime

import requests
from bs4 import BeautifulSoup

from sipp import models as sipp


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

    price_point = sipp.PricePoint.objects.create(
        fund=fund,
        date=price_date,
        price_pence=price_value,
    )

    return price_point

