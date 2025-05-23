from django.core.management.base import BaseCommand
from django.db import models as db
from typing_extensions import Unpack

from ... import models as sipp
from ...utils import exists, Kwargs


class Command(BaseCommand):
    help = 'Records the latest price points for all funds.'

    def handle(self, **_: Unpack[Kwargs]) -> None:
        for portfolio in sipp.Portfolio:
            self.display_single_portfolio(portfolio)


    def display_single_portfolio(self, portfolio: sipp.Portfolio) -> None:

        funds_with_holdings = sipp.Fund.objects.annotate(
            total_quantity=db.Sum(
                db.Case(db.When(
                    holdings__portfolio=portfolio,
                    holdings__sold_on__isnull=True,
                    then='holdings__quantity',
                )),
                default=0.0,
                output_field=db.FloatField(),
            ),
        ).filter(total_quantity__gt=0.0)

        portfolio_value = 0.0
        self.stdout.write('╔══════════╤════════════════════╤════════════════════════════════╤════════════╗')  # noqa: E501
        self.stdout.write('║  Value   │ Breakdown          │ Fund                           │ Date       ║')  # noqa: E501
        self.stdout.write('╠══════════╪════════════════════╪════════════════════════════════╪════════════╣')  # noqa: E501
        for fund in funds_with_holdings:

            price_point = exists(fund.price_points.last())
            holding_value = fund.total_quantity * price_point.pounds
            portfolio_value += holding_value

            self.stdout.write('║ £{:7.2f} │ {:6.2f} x  £{:7.4f} │ {:30} │ {} ║'.format(
                holding_value,
                fund.total_quantity,
                price_point.pounds,
                fund.short_name,
                price_point.date.isoformat(),
            ))

        self.stdout.write('╚══════════╧════════════════════╧════════════════════════════════╧════════════╝')  # noqa: E501
        self.stdout.write('Total {} Portfolio Value: £{:,.2f}'.format(portfolio, portfolio_value))

