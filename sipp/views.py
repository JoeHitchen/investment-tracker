from typing import TypedDict, Any, Callable, TYPE_CHECKING
from datetime import date, timedelta

from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.db import models as db

from . import models, utils


if TYPE_CHECKING:
    PortfolioView = DetailView[models.Portfolio]
    PortfolioQuerySet = db.QuerySet[models.Portfolio]
else:
    PortfolioView = DetailView
    PortfolioQuerySet = db.QuerySet


ContextKwargs = dict[str, Any]
ContextDict = dict[str, Any]

SortFunc = Callable[['FundData'], int | float]


class FundData(TypedDict):
    id: int
    name: str
    price_date: date
    total_cost: float
    total_value: float
    total_profit_loss: float
    growth_rate: float
    growth_aer: float
    active_holdings: list[models.Holding]


class IndexView(TemplateView):
    template_name = 'sipp/index.html'

    @staticmethod
    def sort_func(sort_key: str) -> SortFunc:

        key = {
            'fnd': 'id',
            'val': 'total_value',
            'cst': 'id',
            'pl': 'total_profit_loss',
            'gr': 'growth_rate',
            'aer': 'growth_aer',
        }.get(sort_key.strip('-'), 'id')

        sign = 1 if sort_key and sort_key[0] == '-' else -1
        if key == 'id':
            sign *= -1

        return (lambda fund: sign * fund[key])  # type: ignore


    @staticmethod
    def aggregate_holdings(portfolio: models.Portfolio, sort_func: SortFunc) -> list[FundData]:

        fund_holdings: dict[models.Fund, list[models.Holding]] = {}
        for holding in portfolio.active_holdings():
            if holding.fund not in fund_holdings:
                fund_holdings[holding.fund] = []
            fund_holdings[holding.fund].append(holding)

        fund_data: list[FundData] = []
        for fund, holdings in fund_holdings.items():
            total_cost = sum(holding.cost for holding in holdings)
            total_value = sum(holding.value for holding in holdings)
            fund_data.append({
                'id': fund.id,
                'name': fund.short_name,
                'price_date': fund.latest_price_point.date,
                'total_cost': total_cost,
                'total_value': total_value,
                'total_profit_loss': total_value - total_cost,
                'growth_rate': 100 * (total_value - total_cost) / total_cost,
                'growth_aer': 100 * utils.calculate_aer(holdings),
                'active_holdings': holdings,
            })

        return sorted(fund_data, key = sort_func)


    def get_context_data(self, **kwargs: ContextKwargs) -> ContextDict:
        context = super().get_context_data(**kwargs)
        fund_sort = self.request.GET.get('sort', '')

        price_point_prefetch = db.Prefetch(
            'fund__price_points',
            models.PricePoint.objects.all().order_by('-date'),
            to_attr='_latest_price_points',
        )

        portfolios = models.Portfolio.objects.prefetch_related(  # type: ignore
            db.Prefetch(
                'holdings',
                (
                    models.Holding.objects  # type: ignore
                    .filter(sold_on__isnull=True)
                    .select_related('fund')
                    .prefetch_related(price_point_prefetch)
                ),
                to_attr = '_active_holdings',
            ),
            db.Prefetch(
                'holdings',
                models.Holding.objects.filter(sold_on__isnull=False),
                to_attr = '_closed_holdings',
            ),
        )

        context['portfolios'] = []
        for portfolio in portfolios:

            cash_cost = sum(holding.cost for holding in portfolio.closed_holdings())
            cash_value = sum(holding.value for holding in portfolio.closed_holdings())
            cash_profit_loss = cash_value - cash_cost
            cash_properties = {
                'cost': cash_cost,
                'value': cash_value,
                'profit_loss': cash_profit_loss,
                'growth_rate': 100 * cash_profit_loss / (cash_cost or 1),
                'growth_aer': 100 * utils.calculate_aer(portfolio.closed_holdings()),
            }

            grand_cost = portfolio.total_cost + cash_properties['cost']
            grand_profit_loss = portfolio.total_profit_loss + cash_properties['profit_loss']
            all_holdings = list(portfolio.closed_holdings()) + list(portfolio.active_holdings())
            grand_total_properties = {
                'cost': grand_cost,
                'value': portfolio.total_value + cash_properties['value'],
                'profit_loss': grand_profit_loss,
                'growth_rate': 100 * grand_profit_loss / grand_cost,
                'growth_aer': 100 * utils.calculate_aer(all_holdings),
            }
            context['portfolios'].append((
                portfolio,
                self.aggregate_holdings(portfolio, self.sort_func(fund_sort)),
                cash_properties,
                grand_total_properties,
            ))

        return context


class PortfolioGraphView(PortfolioView):
    template_name = 'sipp/portfolio-graphs.html'
    model = models.Portfolio

    def get_object(self, queryset: PortfolioQuerySet | None = None) -> models.Portfolio:
        return self.model.objects.get(type = self.kwargs['portfolio'])

    @staticmethod
    def _get_fund_price_data(fund: models.Fund, days: list[date]) -> dict[date, float]:

        fund_prices = dict.fromkeys(days, 0.0)
        for price_point in fund.price_points.filter(date__gte = days[0]):
            fund_prices[price_point.date] = price_point.pounds

        prev_price = 0.0
        for day, price in fund_prices.items():
            if not price:
                fund_prices[day] = prev_price
                continue
            prev_price = price

        prev_price = 0.0
        for day, price in list(fund_prices.items())[::-1]:
            if not price:
                fund_prices[day] = prev_price
                continue
            prev_price = price

        return fund_prices

    @staticmethod
    def _calculate_fund_value(units: float, price: float, _: float) -> float:
        return units * price

    @staticmethod
    def _calculate_fund_profit_loss(units: float, price: float, costs: float) -> float:
        return units * price - costs

    def get_context_data(self, **kwargs: ContextKwargs) -> ContextDict:
        context = super().get_context_data(**kwargs)
        context['profit_loss'] = context['view'].kwargs['profit_loss']

        context['start_date'] = {
            models.Portfolio.Types.SIPP: date(2025, 4, 10),
            models.Portfolio.Types.ISA: date(2025, 5, 2),
        }[context['portfolio'].type]

        graph_data_func = {
            False: self._calculate_fund_value,
            True: self._calculate_fund_profit_loss,
        }[context['profit_loss']]

        context['end_date'] = date.today()
        all_days = [
            context['start_date'] + timedelta(i)
            for i in range(0, (context['end_date'] - context['start_date']).days + 1)
        ]

        context['fund_data'] = []
        portfolio_values = dict.fromkeys(all_days, 0.0)
        for fund in list(models.Fund.objects.all())[::-1]:

            holdings = list(fund.holdings.filter(portfolio = context['portfolio']))
            if not len(holdings):
                continue

            costs = dict.fromkeys(all_days, 0.0)
            units_held = dict.fromkeys(all_days, 0.0)
            for holding in holdings:
                holding_end = holding.sold_on or (date.today() + timedelta(1))
                for i in range(0, (holding_end - holding.bought_on).days):
                    costs[holding.bought_on + timedelta(i)] += holding.cost
                    units_held[holding.bought_on + timedelta(i)] += holding.quantity

            fund_prices = self._get_fund_price_data(fund, list(units_held.keys()))
            fund_values = {
                day: round(graph_data_func(units, fund_prices[day], costs[day]), 2)
                for day, units in units_held.items()
            }
            for day, value in fund_values.items():
                portfolio_values[day] += value

            context['fund_data'].append({
                'fund_name': fund.short_name,
                'price_points': [{
                    'x': day.isoformat(),
                    'y': value,
                } for day, value in fund_values.items()],
            })

        context['portfolio_values'] = [{
            'x': day.isoformat(),
            'y': round(value, 2),
        } for day, value in portfolio_values.items()]
        return context

