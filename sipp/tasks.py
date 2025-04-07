from django.utils import timezone
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
    price_point = sipp.PricePoint.objects.create(
        fund=fund,
        date=timezone.now(),
        price_pence=price_value,
    )

    return price_point

