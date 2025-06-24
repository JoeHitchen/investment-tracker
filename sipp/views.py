from typing import Any

from django.views.generic.base import TemplateView
from django.db import models as db

from . import models, utils


ContextKwargs = dict[str, Any]
ContextDict = dict[str, Any]


class IndexView(TemplateView):
    template_name = 'sipp/index.html'

    def get_context_data(self, **kwargs: ContextKwargs) -> ContextDict:
        context = super().get_context_data(**kwargs)

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
            context['portfolios'].append((portfolio, cash_properties, grand_total_properties))

        return context

