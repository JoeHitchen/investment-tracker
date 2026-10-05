from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from firefly_iii_client.models.transaction_split import TransactionSplit as Transaction
from firefly_iii_client.models.transaction_type_property import TransactionTypeProperty

from .client import get_account_transactions
from . import utils



ISA_REPORT_START = date(2023, 4, 6)


def is_isa_contribution(transaction: Transaction) -> bool:
    """Returns a boolean indicating whether the transaction represents a contribution to an ISA."""

    # Withdrawals never count as ISA contributions
    if transaction.type not in (TransactionTypeProperty.DEPOSIT, TransactionTypeProperty.TRANSFER):
        return False

    # Transfers only qualify if they do not come from another ISA account
    if transaction.type == TransactionTypeProperty.TRANSFER:
        return transaction.source_id not in utils.ISA_ACCOUNTS

    # Any other non-interest deposits also count as contributions
    return (
        transaction.source_id != utils.INTEREST_TAX_FREE_SOURCE
        and transaction.category_name != utils.INTEREST_CATEGORY
    )


@dataclass
class MonthlyData:
    """Data on ISA contributions for a single tax month."""

    start_date: date
    by_account: utils.AccountTotals = field(default_factory = lambda: defaultdict(float))

    @property
    def total(self) -> float:
        return sum(self.by_account.values())

    @property
    def has_started(self) -> bool:
        return self.start_date <= date.today()


@dataclass
class AnnualReport:
    """Data on ISA contributions from a single UK tax year."""

    start_year: int
    months: list[MonthlyData] = field(init = False)

    def __post_init__(self) -> None:
        self.months = [MonthlyData(start) for start in utils.tax_month_starts(self.start_year)]

    @property
    def label(self) -> str:
        return f'{self.start_year}/{str(self.start_year + 1)[-2:]}'

    @property
    def by_account(self) -> utils.AccountTotals:
        return utils.sum_account_totals(month.by_account for month in self.months)

    @property
    def total(self) -> float:
        return sum(row.total for row in self.months)

    @property
    def is_partial(self) -> bool:
        return date(self.start_year + 1, 4, 5) >= date.today()


def build_isa_contribution_reports() -> Iterable[AnnualReport]:

    report_years = range(
        utils.tax_year_and_month(ISA_REPORT_START)[0],
        utils.tax_year_and_month(date.today())[0] + 1,
    )
    reports = {year: AnnualReport(year) for year in report_years}

    for account_id in utils.ISA_ACCOUNTS:
        for transaction in get_account_transactions(account_id, ISA_REPORT_START, date.today()):
            if not is_isa_contribution(transaction):
                continue
            tax_year, month = utils.tax_year_and_month(transaction.var_date.date())
            reports[tax_year].months[month].by_account[account_id] += float(transaction.amount)

    return reports.values()
