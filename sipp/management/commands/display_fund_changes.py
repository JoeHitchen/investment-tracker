from datetime import date
from typing import TypedDict
from argparse import ArgumentParser

from django.core.management.base import BaseCommand
from typing_extensions import Unpack

from ... import models as sipp
from ...utils import exists, Kwargs


class FundWithPerformance(TypedDict):
    fund: sipp.Fund
    first_price: sipp.PricePoint
    latest_price: sipp.PricePoint
    performance: float


def fund_performance(fund_with_performance: FundWithPerformance) -> float:
    return fund_with_performance['performance']


class Command(BaseCommand):
    help = 'Records the latest price points for all funds.'

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            'start_date',
            nargs = '?',
            type = date.fromisoformat,
            default = date(2025, 4, 9),
            help = 'The start date of the evaluation window.',
        )

    def handle(self, start_date: date, **_: Unpack[Kwargs]) -> None:

        funds_with_performance: list[FundWithPerformance] = []
        for fund in sipp.Fund.objects.all():
            first_price = exists(fund.price_points.filter(date__gte = start_date).first())
            latest_price = exists(fund.price_points.last())
            price_change = latest_price.hundredths - first_price.hundredths
            funds_with_performance.append({
                'fund': fund,
                'first_price': first_price,
                'latest_price': latest_price,
                'performance': price_change / first_price.hundredths,
            })
        funds_with_performance.sort(reverse = True, key = fund_performance)

        self.stdout.write('╔════════╤════════════════════════════════╤══════════════════════╗')
        self.stdout.write('║ Growth │ Fund                           │  Change              ║')
        self.stdout.write('╠════════╪════════════════════════════════╪══════════════════════╣')
        for fund_with_performance in funds_with_performance:
            self.stdout.write('║ {:5.2f}% │ {:30} │ {:8.4f} -> {:8.4f} ║'.format(
                100 * fund_with_performance['performance'],
                fund_with_performance['fund'].short_name,
                fund_with_performance['first_price'].pounds,
                fund_with_performance['latest_price'].pounds,
            ))
        self.stdout.write('╚═════════════════════════════════════════╧══════════════════════╝')

