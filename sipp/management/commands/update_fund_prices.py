from typing import TypedDict

from django.core.management import BaseCommand, call_command
from typing_extensions import Unpack

from ... import models as sipp
from ...tasks import get_latest_fund_price


class CmdArgs(TypedDict):
    pass


class Command(BaseCommand):
    help = 'Records the latest price points for all funds.'

    def handle(self, **_: Unpack[CmdArgs]) -> None:

        self.stdout.write(' Price   │ Date       │ Fund')
        self.stdout.write('═════════╪════════════╪═══════════════════════')
        for fund in sipp.Fund.objects.all():
            try:
                price_point = get_latest_fund_price(fund)
                self.stdout.write('{:7.2f}p │ {} │ {}'.format(
                    price_point.pence,
                    price_point.date.isoformat(),
                    fund,
                ))
            except Exception as err:
                self.stdout.write(f'Error getting latest price point for {fund.short_name}')
                self.stderr.write(f'{err}')

        self.stdout.write('')
        call_command('display_portfolio_value')

