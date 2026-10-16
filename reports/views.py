from datetime import date
from typing import Any

from django.conf import settings
from django.views.generic.base import TemplateView

from . import consistency_checks, isa_contributions, interest, utils


ContextDict = dict[str, Any]


class IsaReport(TemplateView):
    template_name = 'reports/isa-report.html'

    def get_context_data(self, **kwargs: Any) -> ContextDict:
        context = super().get_context_data(**kwargs)

        context['accounts'] = utils.ISA_ACCOUNTS
        context['reports'] = isa_contributions.build_isa_contribution_reports()

        return context


class InterestReport(TemplateView):
    template_name = 'reports/interest-report.html'

    def get_context_data(self, **kwargs: Any) -> ContextDict:
        context = super().get_context_data(**kwargs)
        context['firefly_public_domain'] = settings.FIREFLY_PUBLIC_DOMAIN

        context['reports'], context['accounts'] = interest.build_interest_reports()

        start_date = interest.INTEREST_REPORT_START
        end_date = date.today()

        context['missing_category'] = consistency_checks.find_missing_interest_category(
            start_date,
            end_date,
        )
        context['unexpected_source'] = consistency_checks.find_unexpected_interest_accounts(
            start_date,
            end_date,
        )
        context['tax_free_not_isa'] = consistency_checks.find_tax_free_non_isa_interest(
            start_date,
            end_date,
        )
        context['taxable_isa'] = consistency_checks.find_taxable_isa_interest(start_date, end_date)

        return context
