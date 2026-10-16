from collections import defaultdict
from datetime import date, timedelta
from typing import Iterable


AccountTotals = dict[str, float]

INTEREST_CATEGORY = 'Interest'
INTEREST_TAXABLE_SOURCE = '32'
INTEREST_TAX_FREE_SOURCE = '48'

INTEREST_SOURCES: dict[str, str] = {
    INTEREST_TAXABLE_SOURCE: 'Interest (Taxable)',
    INTEREST_TAX_FREE_SOURCE: 'Interest (Tax-free)',
}
INTEREST_DESTINATIONS: dict[str, str] = {
    '56': 'Debt Interest',
}

ISA_ACCOUNTS: dict[str, str] = {
    '10': 'HL Chetwood ISA (Flexible)',
    '8': 'HL Chetwood ISA (12 Month)',
    '6': 'HL Chetwood ISA (24 Month)',
    '24': 'HL S&S ISA',
    '3': 'Skipton ISA',
    '64': 'Santander ISA',
    '68': 'Nationwide ISA',
    '69': 'Nutmeg ISA',
}


def tax_year_and_month(when: date) -> tuple[int, int]:
    """Returns the UK tax year and zero-indexed tax month for the date provided."""

    shifted = when - timedelta(days = 5)
    tax_year = shifted.year if shifted.month >= 4 else shifted.year - 1
    return tax_year, (shifted.month - 4) % 12


def tax_month_starts(start_year: int) -> list[date]:
    """Returns the start dates of the 12 tax months in the tax year starting in `start_year`."""

    return [
        date(start_year + calendar_month // 12, calendar_month % 12 + 1, 6)
        for calendar_month in range(3, 15)  # 3 = April, 15 = April+1
    ]


def sum_account_totals(parts: Iterable[AccountTotals]) -> AccountTotals:
    """Returns the sum of the account totals in `parts`."""
    totals: AccountTotals = defaultdict(float)
    for part in parts:
        for account_id, amount in part.items():
            totals[account_id] += amount
    return totals

