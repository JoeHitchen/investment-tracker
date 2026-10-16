from collections.abc import Iterator
from datetime import date

from firefly_iii_client.api.accounts_api import AccountsApi
from firefly_iii_client.api.search_api import SearchApi
from firefly_iii_client.api_client import ApiClient
from firefly_iii_client.models.transaction_split import TransactionSplit
from firefly_iii_client.configuration import Configuration
# ^ N.B. This is not the same as `firefly_iii_client.Configuration`

from core import settings


PAGE_SIZE = 1000


def get_client() -> ApiClient:
    """Builds a configured Firefly III API client."""

    configuration = Configuration(
        host = settings.FIREFLY_API_URL,
        access_token = settings.FIREFLY_API_TOKEN,
    )
    return ApiClient(configuration)


def get_account_transactions(
    account_id: str,
    start: date,
    end: date,
) -> Iterator[TransactionSplit]:
    """Yields every transaction split for the account in the given date range.

    Where a primary transaction is divided into multiple splits, Firefly checks and returns each
    split individually, so every relevant split but no extraneous splits are returned and no
    additional filtering is required.

    Transaction "amount" is always positive."""

    accounts_api = AccountsApi(get_client())
    page = 1
    while True:
        response = accounts_api.list_transaction_by_account(
            id = account_id,
            start = start,
            end = end,
            limit = PAGE_SIZE,
            page = page,
        )
        for transaction in response.data:
            yield from transaction.attributes.transactions or []

        pagination = response.meta.pagination
        total_pages = pagination.total_pages if pagination and pagination.total_pages else 1
        if page >= total_pages:
            break
        page += 1


def search_transactions(query: str, start: date, end: date) -> list[tuple[str, TransactionSplit]]:
    """Returns the ID of the transaction group and split, of every transaction matching the query.

    Where a primary transaction is divided into multiple splits, Firefly checks and returns each
    split individually, so every relevant split but no extraneous splits are returned and no
    additional filtering is required.

    The date range on the function signature is _inclusive_ of both dates."""

    page = 1
    search_api = SearchApi(get_client())
    transactions_with_groups: list[tuple[str, TransactionSplit]] = []
    while True:
        response = search_api.search_transactions(
            query = f'{query} date_after:{start} date_before:{end}',  # Both inclusive
            limit = PAGE_SIZE,
            page = page,
        )
        for group in response.data:
            for transaction in group.attributes.transactions or []:
                transactions_with_groups.append((group.id, transaction))

        pagination = response.meta.pagination
        total_pages = pagination.total_pages if pagination and pagination.total_pages else 1
        if page >= total_pages:
            break
        page += 1

    return transactions_with_groups
