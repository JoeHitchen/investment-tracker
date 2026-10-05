from typing import Any

from django.views.generic.base import TemplateView

from . import isa_contributions, utils


ContextDict = dict[str, Any]


class IsaReport(TemplateView):
    template_name = 'reports/isa-report.html'

    def get_context_data(self, **kwargs: Any) -> ContextDict:
        context = super().get_context_data(**kwargs)

        context['accounts'] = utils.ISA_ACCOUNTS
        context['reports'] = isa_contributions.build_isa_contribution_reports()

        return context
