from datetime import date
from typing import Iterable

from firefly_iii_client.models.transaction_split import TransactionSplit as Transaction

from .client import search_transactions
from . import utils


TransactionWithGroup = tuple[str, Transaction]


def _sort_by_date(items: Iterable[TransactionWithGroup]) -> list[TransactionWithGroup]:
    return sorted(items, key = lambda item: item[1].var_date, reverse = True)


def find_missing_interest_category(start_date: date, end_date: date) -> list[TransactionWithGroup]:
    """Finds transactions to or from interest accounts, which are missing the interest category."""

    transactions: list[TransactionWithGroup] = []
    for source in utils.INTEREST_SOURCES:
        transactions.extend(
            search_transactions(
                f'source_account_id:{source} -category_is:"{utils.INTEREST_CATEGORY}"',
                start_date,
                end_date,
            ),
        )
    for destination in utils.INTEREST_DESTINATIONS:
        transactions.extend(
            search_transactions(
                f'destination_account_id:{destination}'
                + f' -category_is:"{utils.INTEREST_CATEGORY}"',
                start_date,
                end_date,
            ),
        )
    return _sort_by_date(transactions)


def find_unexpected_interest_accounts(
    start_date: date,
    end_date: date,
) -> list[TransactionWithGroup]:
    """Finds transactions in the interest category but not to or from an interest account."""

    query = f'category_is:"{utils.INTEREST_CATEGORY}"'
    for source in utils.INTEREST_SOURCES:
        query += f' -source_account_id:{source}'
    for destination in utils.INTEREST_DESTINATIONS:
        query += f' -destination_account_id:{destination}'

    return _sort_by_date(search_transactions(query, start_date, end_date))


def find_tax_free_non_isa_interest(start_date: date, end_date: date) -> list[TransactionWithGroup]:
    """Finds tax-free interest which was paid into a non-ISA account."""

    query = f'source_account_id:{utils.INTEREST_TAX_FREE_SOURCE}'
    for isa_account in utils.ISA_ACCOUNTS:
        query += f' -destination_account_id:{isa_account}'

    return _sort_by_date(search_transactions(query, start_date, end_date))


def find_taxable_isa_interest(start_date: date, end_date: date) -> list[TransactionWithGroup]:
    """Finds taxable interest which was paid into an ISA account.

    N.B. Firefly does not support OR filtering, so checking if the destination is in a list of
    accounts must be done in Python."""

    taxable_interest = search_transactions(
        f'source_account_id:{utils.INTEREST_TAXABLE_SOURCE}',
        start_date,
        end_date,
    )

    taxable_isa_interest: list[TransactionWithGroup] = []
    for group_id, transaction in taxable_interest:
        if transaction.destination_id in utils.ISA_ACCOUNTS:
            taxable_isa_interest.append((group_id, transaction))

    return _sort_by_date(taxable_isa_interest)
