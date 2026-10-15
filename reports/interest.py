from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from firefly_iii_client.models.transaction_split import TransactionSplit as Transaction
from firefly_iii_client.models.transaction_type_property import TransactionTypeProperty

from .client import get_account_transactions
from . import utils


INTEREST_REPORT_START = date(2023, 4, 6)


def is_interest_received(transaction: Transaction) -> bool:
    """Returns a boolean indicating whether the transaction represents interest received."""

    return (
        transaction.type == TransactionTypeProperty.DEPOSIT
        and transaction.source_id in utils.INTEREST_SOURCES
    )


def is_taxable_interest(transaction: Transaction) -> bool:
    """Returns a boolean indicating whether the interest is taxable."""

    return (
        transaction.source_id != utils.INTEREST_TAX_FREE_SOURCE
        and transaction.destination_id not in utils.ISA_ACCOUNTS
    )


@dataclass
class MonthlyData:
    """Interest received in a single tax month, by receiving account."""

    start_date: date
    taxable_by_account: utils.AccountTotals = field(default_factory = lambda: defaultdict(float))
    tax_free_by_account: utils.AccountTotals = field(default_factory = lambda: defaultdict(float))

    @property
    def taxable(self) -> float:
        return sum(self.taxable_by_account.values())

    @property
    def tax_free(self) -> float:
        return sum(self.tax_free_by_account.values())

    @property
    def total(self) -> float:
        return self.taxable + self.tax_free

    @property
    def has_started(self) -> bool:
        return self.start_date <= date.today()


@dataclass
class AnnualReport:
    """Data on interest received in a single UK tax year."""

    start_year: int
    months: list[MonthlyData] = field(init = False)

    def __post_init__(self) -> None:
        self.months = [MonthlyData(start) for start in utils.tax_month_starts(self.start_year)]

    @property
    def label(self) -> str:
        return f'{self.start_year}/{str(self.start_year + 1)[-2:]}'

    @property
    def taxable_by_account(self) -> utils.AccountTotals:
        return utils.sum_account_totals(month.taxable_by_account for month in self.months)

    @property
    def tax_free_by_account(self) -> utils.AccountTotals:
        return utils.sum_account_totals(month.tax_free_by_account for month in self.months)

    @property
    def taxable(self) -> float:
        return sum(month.taxable for month in self.months)

    @property
    def tax_free(self) -> float:
        return sum(month.tax_free for month in self.months)

    @property
    def total(self) -> float:
        return self.taxable + self.tax_free

    @property
    def total_accounts(self) -> int:
        return len(self.taxable_by_account) + len(self.tax_free_by_account)

    @property
    def is_partial(self) -> bool:
        return date(self.start_year + 1, 4, 5) >= date.today()


def build_interest_reports() -> tuple[Iterable[AnnualReport], dict[str, str]]:
    """Returns the annual reports, and the names of the accounts that received interest."""

    today = date.today()
    report_years = range(
        utils.tax_year_and_month(INTEREST_REPORT_START)[0],
        utils.tax_year_and_month(today)[0] + 1,
    )
    reports = {year: AnnualReport(year) for year in report_years}
    account_names: dict[str, str] = {}

    for source_id in utils.INTEREST_SOURCES:
        for transaction in get_account_transactions(source_id, INTEREST_REPORT_START, today):
            if not is_interest_received(transaction):
                continue

            account_id = transaction.destination_id
            if account_id is None:
                continue
            amount = float(transaction.amount)
            account_names[account_id] = transaction.destination_name or account_id

            tax_year, month = utils.tax_year_and_month(transaction.var_date.date())
            data = reports[tax_year].months[month]
            if is_taxable_interest(transaction):
                data.taxable_by_account[account_id] += amount
            else:
                data.tax_free_by_account[account_id] += amount

    return reports.values(), account_names
