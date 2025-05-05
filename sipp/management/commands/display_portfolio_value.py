from django.core.management.base import BaseCommand
from typing_extensions import Unpack

from ... import models as sipp
from ...utils import exists, Kwargs


class Command(BaseCommand):
    help = 'Records the latest price points for all funds.'

    def handle(self, **_: Unpack[Kwargs]) -> None:
        for portfolio in sipp.Portfolio:
            self.display_single_portfolio(portfolio)


    def display_single_portfolio(self, portfolio: sipp.Portfolio) -> None:

        portfolio_value = 0.0
        self.stdout.write('╔═════════╤════════════════════╤════════════════════════════════╤════════════╗')  # noqa: E501
        self.stdout.write('║ Value   │ Breakdown          │ Fund                           │ Date       ║')  # noqa: E501
        self.stdout.write('╠═════════╪════════════════════╪════════════════════════════════╪════════════╣')  # noqa: E501
        for holding in sipp.Holding.objects.filter(portfolio=portfolio, sold_on__isnull=True):

            price_point = exists(holding.fund.price_points.last())
            holding_value = holding.quantity * price_point.pounds
            portfolio_value += holding_value

            self.stdout.write('║ £{:6.2f} │ {:6.2f} x  £{:7.4f} │ {:30} │ {} ║'.format(
                holding_value,
                holding.quantity,
                price_point.pounds,
                holding.fund.short_name,
                price_point.date.isoformat(),
            ))

        self.stdout.write('╚═════════╧════════════════════╧════════════════════════════════╧════════════╝')  # noqa: E501
        self.stdout.write('Total {} Portfolio Value: £{:,.2f}'.format(portfolio, portfolio_value))

