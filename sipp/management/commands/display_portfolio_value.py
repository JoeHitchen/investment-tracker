from datetime import date
from argparse import ArgumentParser

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models as db
from typing_extensions import Unpack

from ... import models as sipp
from ...utils import Kwargs


class PortfolioKwargs(Kwargs):
    eval_date: date


class Command(BaseCommand):
    help = 'Displays the valuation of the portfolio.'

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            'eval_date',
            type = date.fromisoformat,
            nargs = '?',
            default = str(timezone.now().date()),
            help = 'The date of portfolio evaluation (default: today).',
        )


    def handle(self, **kwargs: Unpack[PortfolioKwargs]) -> None:
        for portfolio in sipp.Portfolio.objects.all():
            self.display_single_portfolio(portfolio, kwargs['eval_date'])


    def display_single_portfolio(self, portfolio: sipp.Portfolio, eval_date: date) -> None:

        funds_with_holdings = sipp.Fund.objects.annotate(  # type: ignore
            total_quantity=db.Sum(
                db.Case(db.When(
                    holdings__portfolio=portfolio,
                    holdings__bought_on__lte=eval_date,
                    holdings__sold_on__isnull=True,
                    then='holdings__quantity',
                )),
                default=0.0,
                output_field=db.FloatField(),
            ),
        ).prefetch_related(db.Prefetch(
            'price_points',
            sipp.PricePoint.objects.filter(date__lte=eval_date).order_by('-date'),
            to_attr='_latest_price_points',
        )).filter(total_quantity__gt=0.0)

        portfolio_value = 0.0
        self.stdout.write('╔══════════╤══════════════════════╤════════════════════════════════╤════════════╗')  # noqa: E501
        self.stdout.write('║  Value   │ Breakdown            │ Fund                           │ Date       ║')  # noqa: E501
        self.stdout.write('╠══════════╪══════════════════════╪════════════════════════════════╪════════════╣')  # noqa: E501
        for fund in funds_with_holdings:

            price_point = fund.latest_price_point
            holding_value = fund.total_quantity * price_point.pounds
            portfolio_value += holding_value

            self.stdout.write('║ £{:7.2f} │ {:7.2f} x  £{:8.4f} │ {:30} │ {} ║'.format(
                holding_value,
                fund.total_quantity,
                price_point.pounds,
                fund.short_name,
                price_point.date.isoformat(),
            ))

        self.stdout.write('╚══════════╧══════════════════════╧════════════════════════════════╧════════════╝')  # noqa: E501
        self.stdout.write('Total {} Portfolio Value: £{:,.2f}'.format(portfolio, portfolio_value))

