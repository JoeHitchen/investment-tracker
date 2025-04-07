from typing import TypedDict, TypeVar

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from typing_extensions import Unpack

from ... import models as sipp
from ...tasks import get_latest_fund_price


Obj = TypeVar('Obj')


def exists(obj: Obj | None) -> Obj:
    assert obj
    return obj


class CmdArgs(TypedDict):
    pass


class Command(BaseCommand):
    help = 'Records the latest price points for all funds.'

    def handle(self, **_: Unpack[CmdArgs]) -> None:

        portfolio_value = 0.0
        self.stdout.write('Value                       Fund')
        self.stdout.write('==============================================')
        for fund in sipp.Fund.objects.all():

            try:
                price_point = get_latest_fund_price(fund)
            except IntegrityError:
                price_point = exists(fund.price_points.order_by('-date').first())
            except Exception as err:
                self.stdout.write(f'Error getting latest price point for {fund.short_name}')
                self.stderr.write(f'{err}')
                price_point = exists(fund.price_points.order_by('-date').first())

            fund_value = (fund.bought_quantity / 100) * price_point.price
            portfolio_value += fund_value

            self.stdout.write('{0:.2f}  ({1:6.2f} @ {2:7.2f})  {3}'.format(
                fund_value,
                fund.bought_quantity,
                price_point.price,
                fund.short_name),
            )

        self.stdout.write('==============================================')
        self.stdout.write('Total Portfolio Value: £{0:,.2f}'.format(portfolio_value))

