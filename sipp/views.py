from typing import Any

from django.views.generic.base import TemplateView
from django.db import models as db

from . import models


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

        holding_prefetch = db.Prefetch(
            'holdings',
            (
                models.Holding.objects
                .filter(sold_on__isnull=True)
                .select_related('fund')
                .prefetch_related(price_point_prefetch)
            ),
            to_attr = '_active_holdings',
        )

        context['portfolios'] = []
        for portfolio in models.Portfolio.objects.all().prefetch_related(holding_prefetch):
            context['portfolios'].append(portfolio)

        return context

