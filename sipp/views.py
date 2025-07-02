from typing import TypedDict, Any, Callable

from django.views.generic.base import TemplateView
from django.db import models as db

from . import models, utils


ContextKwargs = dict[str, Any]
ContextDict = dict[str, Any]

SortFunc = Callable[['FundData'], int | float]


class FundData(TypedDict):
    id: int
    name: str
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

        portfolios = models.Portfolio.objects.prefetch_related(
            db.Prefetch(
                'holdings',
                (
                    models.Holding.objects
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

