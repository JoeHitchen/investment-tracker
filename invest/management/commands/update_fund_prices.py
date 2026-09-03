from typing import Unpack
import logging

from django.core.management import BaseCommand, call_command

from ... import models as invest
from ...utils import Kwargs
from ...tasks import refresh_fund_price

logging.basicConfig(level = logging.INFO)


class Command(BaseCommand):
    help = 'Records the latest price points for all funds.'

    def handle(self, **_: Unpack[Kwargs]) -> None:

        for fund in invest.Fund.objects.filter(monitor_price=True):
            try:
                refresh_fund_price(fund)
            except Exception as err:
                self.stdout.write(f'Error getting latest price point for {fund.short_name}')
                self.stderr.write(f'{err}')

        self.stdout.write('')
        call_command('display_portfolio_value')

