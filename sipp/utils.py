from typing import TypedDict, TypeVar, Iterable, TYPE_CHECKING

from django.utils import timezone
import pyxirr

if TYPE_CHECKING:
    from .models import Holding


Obj = TypeVar('Obj')


class Kwargs(TypedDict):
    pass


def exists(obj: Obj | None) -> Obj:
    assert obj
    return obj


def calculate_aer(holdings: Iterable['Holding']) -> float:
    """Calculates an approximate Annual Equivalent [Growth] Rate (AER) for a set of holdings."""

    if not len(list(holdings)):
        return 0.0

    transactions = {}
    today = timezone.now().date()
    for holding in holdings:

        if holding.bought_on not in transactions:
            transactions[holding.bought_on] = 0.0
        transactions[holding.bought_on] += holding.cost

        holding_end_date = holding.sold_on if holding.sold_on else today
        if holding_end_date not in transactions:
            transactions[holding_end_date] = 0.0
        transactions[holding_end_date] -= holding.value

    transaction_dates = []
    transaction_values = []
    for date in sorted(transactions.keys()):
        transaction_dates.append(date)
        transaction_values.append(transactions[date])

    return exists(pyxirr.xirr(transaction_dates, transaction_values))

