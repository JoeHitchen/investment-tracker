from datetime import date, datetime, timedelta, time
from unittest.mock import patch

from django.test import TestCase
from django.db.models import QuerySet
from django.utils import timezone

from invest.models import Portfolio, Fund, Holding, PricePoint
from invest.templatetags.invest_tags import is_todays_price
from invest.utils import exists, calculate_aer


class Test_Portfolio(TestCase):

    portfolio: Portfolio
    holding_1: Holding
    holding_2: Holding
    holding_3: Holding
    holding_4: Holding

    @classmethod
    def setUpTestData(cls) -> None:
        cls.portfolio = Portfolio.objects.get(type=Portfolio.Types.SIPP)

        fund_1 = Fund.objects.create()
        cls.holding_1 = cls.portfolio.holdings.create(
            fund=fund_1,
            quantity=64,
            bought_on=date(2024, 4, 6),
            bought_at=10000,
        )
        fund_1.price_points.create(
            date=date(2025, 5, 18),
            hundredths = 13000,
        )

        fund_2 = Fund.objects.create()
        cls.holding_2 = cls.portfolio.holdings.create(
            fund=fund_2,
            quantity=32,
            bought_on=date(2024, 4, 10),
            bought_at=11000,
        )
        fund_2.price_points.create(
            date=date(2025, 5, 18),
            hundredths = 14300,
        )

        cls.holding_3 = cls.portfolio.holdings.create(
            fund=fund_1,
            quantity=16,
            bought_on=date(2024, 4, 14),
            bought_at=12000,
            sold_on=date(2025, 4, 14),
            sold_at=12500,
        )
        cls.holding_4 = cls.portfolio.holdings.create(
            fund=fund_2,
            quantity=16,
            bought_on=date(2024, 4, 15),
            bought_at=12100,
            sold_on=date(2025, 4, 16),
            sold_at=12600,
        )


    def test__active_holdings__no_cache(self) -> None:
        """Returns the active holdings for the portfolio."""

        self.assertEqual(
            list(self.portfolio.active_holdings()),
            [self.holding_1, self.holding_2],
        )


    def test__active_holdings__cached(self) -> None:
        """Returns the cached active holdings for the portfolio."""

        self.portfolio._active_holdings = [self.holding_1, self.holding_3]
        self.assertEqual(
            self.portfolio.active_holdings(),
            [self.holding_1, self.holding_3],
        )


    def test__active_holdings__empty_cache(self) -> None:
        """An empty cache is acceptable."""

        self.portfolio._active_holdings = []
        self.assertEqual(self.portfolio.active_holdings(), [])


    def test__closed_holdings__no_cache(self) -> None:
        """Returns the closed holdings for the portfolio."""

        self.assertEqual(
            list(self.portfolio.closed_holdings()),
            [self.holding_3, self.holding_4],
        )


    def test__closed_holdings__cached(self) -> None:
        """Returns the closed active holdings for the portfolio."""

        self.portfolio._closed_holdings = [self.holding_2, self.holding_4]
        self.assertEqual(
            self.portfolio.closed_holdings(),
            [self.holding_2, self.holding_4],
        )


    def test__closed_holdings__empty_cache(self) -> None:
        """An empty cache is acceptable."""

        self.portfolio._closed_holdings = []
        self.assertEqual(self.portfolio.closed_holdings(), [])


    def test__total_cost(self) -> None:
        """Returns the total cost of the active holdings."""

        self.assertEqual(self.portfolio.total_cost, 99.20)


    def test__total_value(self) -> None:
        """Returns the total value of the active holdings."""

        self.assertAlmostEqual(self.portfolio.total_value, 128.96)


    def test__total_profit_loss(self) -> None:
        """Returns the total profit or loss of the active holdings."""

        self.assertAlmostEqual(self.portfolio.total_profit_loss, 29.76)


    def test__growth_rate(self) -> None:
        """Returns the growth rate of the active holdings."""

        self.assertAlmostEqual(self.portfolio.growth_rate, 30.00)


    def test__growth_aer(self) -> None:
        """Returns an approximate Annual Equivalent Rate for the active holdings"""

        self.assertAlmostEqual(self.portfolio.growth_aer, 26.63, 2)


class Test_Fund(TestCase):

    portfolio: Portfolio
    fund: Fund
    holding_1: Holding
    holding_2: Holding
    other_holdings: QuerySet[Holding]
    latest_price_point: PricePoint

    @classmethod
    def setUpTestData(cls) -> None:
        cls.portfolio = Portfolio.objects.get(type=Portfolio.Types.SIPP)

        cls.fund = Fund.objects.create()
        cls.holding_1 = cls.fund.holdings.create(
            portfolio=cls.portfolio,
            quantity=64,
            bought_on=date(2024, 4, 6),
            bought_at=10000,
        )
        cls.holding_2 = cls.fund.holdings.create(
            portfolio=cls.portfolio,
            quantity=32,
            bought_on=date(2024, 4, 10),
            bought_at=11000,
        )
        cls.fund.price_points.create(date=date(2024, 4, 6), hundredths=10000)
        cls.fund.price_points.create(date=date(2024, 4, 10), hundredths=11000)
        cls.latest_price_point = cls.fund.price_points.create(
            date=date(2024, 10, 5),
            hundredths=12000,
        )
        holding_ids = [cls.holding_1.id, cls.holding_2.id]
        cls.other_holdings = cls.fund.holdings.exclude(id__in = holding_ids)


    def test__latest_price__no_cache(self) -> None:
        """Returns the latest price point for the fund directly from the database."""

        self.assertEqual(self.fund.latest_price_point, self.latest_price_point)


    def test__latest_price__with_cache(self) -> None:
        """Uses a cached price point if available."""

        cached_price_point = PricePoint()
        self.fund._latest_price_points = [cached_price_point]

        self.assertEqual(self.fund.latest_price_point, cached_price_point)


    def test__buy__purchase_today(self) -> None:
        """Creates a new holding on the given date, defaulting to today."""

        cost = self.fund.buy(portfolio=self.portfolio, quantity=100)
        self.assertEqual(cost, 120.00)
        self.assertEqual(self.fund.holdings.count(), 3)

        new_holding = exists(self.other_holdings.last())
        self.assertEqual(new_holding.quantity, 100)
        self.assertEqual(new_holding.bought_on, timezone.now().date())
        self.assertEqual(new_holding.bought_at, 12000)
        self.assertIsNone(new_holding.sold_on)
        self.assertIsNone(new_holding.sold_at)


    def test__buy__purchase_historical(self) -> None:
        """Creates a new holding on the given date, defaulting to today."""

        cost = self.fund.buy(portfolio=self.portfolio, quantity=100, date=date(2024, 7, 5))
        self.assertEqual(cost, 110.00)
        self.assertEqual(self.fund.holdings.count(), 3)

        new_holding = exists(self.other_holdings.last())
        self.assertEqual(new_holding.quantity, 100)
        self.assertEqual(new_holding.bought_on, date(2024, 7, 5))
        self.assertEqual(new_holding.bought_at, 11000)
        self.assertIsNone(new_holding.sold_on)
        self.assertIsNone(new_holding.sold_at)


    def test__buy__portfolio_string(self) -> None:
        """Accepts the portfolio as a case-sensitive string."""

        cost = self.fund.buy('SIPP', quantity=100, date=date(2024, 7, 5))
        self.assertEqual(cost, 110.00)
        self.assertEqual(self.fund.holdings.count(), 3)

        new_holding = exists(self.other_holdings.last())
        self.assertEqual(new_holding.quantity, 100)
        self.assertEqual(new_holding.bought_on, date(2024, 7, 5))
        self.assertEqual(new_holding.bought_at, 11000)
        self.assertIsNone(new_holding.sold_on)
        self.assertIsNone(new_holding.sold_at)


    def test__buy__portfolio_invalid(self) -> None:
        """Raises an error if the portfolio is not recognised."""

        with self.assertRaises(Portfolio.DoesNotExist):
            self.fund.buy('savings', quantity=100, date=date(2024, 7, 5))
        self.assertEqual(self.fund.holdings.count(), 2)


    def test__buy__zero_quantity(self) -> None:
        """Raises an error if the purchase is for zero units."""

        with self.assertRaises(AssertionError):
            self.fund.buy(portfolio=self.portfolio, quantity=0)
        self.assertEqual(self.fund.holdings.count(), 2)


    def test__buy__negative_quantity(self) -> None:
        """Raises an error if the purchase is for a negative number of units."""

        with self.assertRaises(AssertionError):
            self.fund.buy(portfolio=self.portfolio, quantity=-1)
        self.assertEqual(self.fund.holdings.count(), 2)


    def test__sell__full_first_holding(self) -> None:
        """Sells all of the first holding."""

        profit_loss = self.fund.sell(portfolio=self.portfolio, quantity=64)
        self.assertAlmostEqual(profit_loss, 12.80)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertEqual(self.holding_1.sold_on, timezone.now().date())
        self.assertFalse(self.holding_1.reinvested)

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertIsNone(self.holding_2.sold_on)


    def test__sell__partial_first_holding(self) -> None:
        """Sells part of the first holding."""

        profit_loss = self.fund.sell(portfolio=self.portfolio, quantity=27)
        self.assertAlmostEqual(profit_loss, 5.40)

        self.assertEqual(self.fund.holdings.count(), 3)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 27)
        self.assertEqual(self.holding_1.sold_on, timezone.now().date())
        self.assertFalse(self.holding_1.reinvested)

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertIsNone(self.holding_2.sold_on)

        new_holding = exists(self.other_holdings.last())
        self.assertEqual(new_holding.quantity, 37)
        self.assertEqual(new_holding.bought_on, self.holding_1.bought_on)
        self.assertEqual(new_holding.bought_at, self.holding_1.bought_at)
        self.assertIsNone(new_holding.sold_on)
        self.assertIsNone(new_holding.sold_at)


    def test__sell__full_both_holdings(self) -> None:
        """Sells all of both holdings."""

        profit_loss = self.fund.sell(portfolio=self.portfolio, quantity=96)
        self.assertAlmostEqual(profit_loss, 16.00)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertEqual(self.holding_1.sold_on, timezone.now().date())
        self.assertFalse(self.holding_1.reinvested)

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertEqual(self.holding_2.sold_on, timezone.now().date())
        self.assertFalse(self.holding_2.reinvested)


    def test__sell__partial_second_holding(self) -> None:
        """Sells all of the first holding and part of the second holding."""

        profit_loss = self.fund.sell(portfolio=self.portfolio, quantity=71)
        self.assertAlmostEqual(profit_loss, 13.5)

        self.assertEqual(self.fund.holdings.count(), 3)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertEqual(self.holding_1.sold_on, timezone.now().date())
        self.assertFalse(self.holding_1.reinvested)

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 7)
        self.assertEqual(self.holding_2.sold_on, timezone.now().date())
        self.assertFalse(self.holding_2.reinvested)

        new_holding = exists(self.other_holdings.last())
        self.assertEqual(new_holding.quantity, 25)
        self.assertEqual(new_holding.bought_on, self.holding_2.bought_on)
        self.assertEqual(new_holding.bought_at, self.holding_2.bought_at)
        self.assertIsNone(new_holding.sold_on)
        self.assertIsNone(new_holding.sold_at)


    def test__sell__oversale(self) -> None:
        """Raises an error if the sale is for more units than are held."""

        with self.assertRaises(AssertionError):
            self.fund.sell(portfolio=self.portfolio, quantity=128)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertIsNone(self.holding_1.sold_on)

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertIsNone(self.holding_2.sold_on)


    def test__sell__zero_quantity(self) -> None:
        """Raises an error if the sale is for a negative number of units."""

        with self.assertRaises(AssertionError):
            self.fund.sell(portfolio=self.portfolio, quantity=0)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertIsNone(self.holding_1.sold_on)

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertIsNone(self.holding_2.sold_on)


    def test__sell__negative_quantity(self) -> None:
        """Raises an error if the sale is for a negative number of units."""

        with self.assertRaises(AssertionError):
            self.fund.sell(portfolio=self.portfolio, quantity=-1)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertIsNone(self.holding_1.sold_on)

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertIsNone(self.holding_2.sold_on)


    def test__sell__yesterday(self) -> None:
        """Records the sale of both holdings against the date provided."""

        profit_loss = self.fund.sell(
            portfolio=self.portfolio,
            quantity=96,
            date=timezone.now().date() - timedelta(5),
        )
        self.assertAlmostEqual(profit_loss, 16.00)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertEqual(self.holding_1.sold_on, timezone.now().date() - timedelta(5))

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertEqual(self.holding_2.sold_on, timezone.now().date() - timedelta(5))


    def test__sell__tomorrow(self) -> None:
        """Raises an error if the sale date is in the future."""

        with self.assertRaises(AssertionError):
            self.fund.sell(
                portfolio=self.portfolio,
                quantity=96,
                date=timezone.now().date() + timedelta(1),
            )

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertIsNone(self.holding_1.sold_on)

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertIsNone(self.holding_2.sold_on)


    def test__sell__reinvested(self) -> None:
        """Propagates the 'reinvested' flag to all sold holdings, but not new holdings."""

        profit_loss = self.fund.sell(portfolio=self.portfolio, quantity=71, reinvested = True)
        self.assertAlmostEqual(profit_loss, 13.5)

        self.assertEqual(self.fund.holdings.count(), 3)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertEqual(self.holding_1.sold_on, timezone.now().date())
        self.assertTrue(self.holding_1.reinvested)

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 7)
        self.assertEqual(self.holding_2.sold_on, timezone.now().date())
        self.assertTrue(self.holding_2.reinvested)

        new_holding = exists(self.other_holdings.last())
        self.assertEqual(new_holding.quantity, 25)
        self.assertEqual(new_holding.bought_on, self.holding_2.bought_on)
        self.assertEqual(new_holding.bought_at, self.holding_2.bought_at)
        self.assertIsNone(new_holding.sold_on)
        self.assertIsNone(new_holding.sold_at)
        self.assertFalse(new_holding.reinvested)


    def test__sell__portfolio_string(self) -> None:
        """Accepts the portfolio as a case-sensitive string."""

        profit_loss = self.fund.sell('SIPP', quantity=64)
        self.assertAlmostEqual(profit_loss, 12.80)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertEqual(self.holding_1.sold_on, timezone.now().date())

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertIsNone(self.holding_2.sold_on)


    def test__sell__portfolio_invalid(self) -> None:
        """Raises an error if the portfolio is not recognised."""

        with self.assertRaises(Portfolio.DoesNotExist):
            self.fund.sell('savings', quantity=64)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertIsNone(self.holding_1.sold_on)

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertIsNone(self.holding_2.sold_on)


class Test_Holding(TestCase):

    fund: Fund
    holding: Holding
    latest_price: PricePoint

    @classmethod
    def setUpTestData(cls) -> None:
        cls.fund = Fund.objects.create()
        cls.holding = cls.fund.holdings.create(
            portfolio=exists(Portfolio.objects.first()),
            quantity=64,
            bought_on=date(2024, 4, 6),
            bought_at=10000,
        )
        cls.fund.price_points.create(date=date(2025, 4, 5), hundredths=10300)
        cls.latest_price = cls.fund.price_points.create(
            date=timezone.now().date(),
            hundredths=10500,
        )


    def test__cost(self) -> None:
        """Returns the original cost of the holding, in pounds."""

        self.assertEqual(self.holding.cost, 64.00)


    def test__end_price__open_holding(self) -> None:
        """Returns the latest price point for the fund, in pounds."""

        self.assertEqual(self.holding.latest_price_point, self.latest_price)
        self.assertEqual(self.holding.end_price, 1.05)


    def test__end_price__closed_holding(self) -> None:
        """Returns the sale price for the fund, in pounds."""

        self.holding.sold_on = timezone.now().date()
        self.holding.sold_at = 11000

        with self.assertRaises(AssertionError):
            self.holding.latest_price_point

        self.assertEqual(self.holding.end_price, 1.10)


    def test__end_price__cached_price_point(self) -> None:
        """Uses cached price points for open holdings, if available."""

        price_point = PricePoint(hundredths = 12000)
        self.holding.fund._latest_price_points = [price_point]

        self.assertEqual(self.holding.latest_price_point, price_point)
        self.assertEqual(self.holding.end_price, 1.20)


    def test__value_profit_loss__still_held_at_profit(self) -> None:
        """Uses the latest price point multiplied by the quantity."""

        self.assertAlmostEqual(self.holding.value, 67.20)
        self.assertAlmostEqual(self.holding.profit_loss, 3.20)
        self.assertAlmostEqual(self.holding.growth_rate, 5.0)


    def test__value_profit_loss__still_held_at_loss(self) -> None:
        """Uses the latest price point multiplied by the quantity."""

        self.latest_price.hundredths = 9500
        self.latest_price.save()

        self.assertAlmostEqual(self.holding.value, 60.80)
        self.assertAlmostEqual(self.holding.profit_loss, -3.20)
        self.assertAlmostEqual(self.holding.growth_rate, -5.0)


    def test__value_profit_loss__sold_at_profit(self) -> None:
        """Uses the sale price provided multiplied by the quantity."""

        self.holding.sold_on = date(2025, 4, 5)
        self.holding.sold_at = 10700
        self.holding.save()

        self.assertAlmostEqual(self.holding.value, 68.48)
        self.assertAlmostEqual(self.holding.profit_loss, 4.48)
        self.assertAlmostEqual(self.holding.growth_rate, 7.0)


    def test__value_profit_loss__sold_at_loss(self) -> None:
        """Uses the sale price provided."""

        self.holding.sold_on = date(2025, 4, 5)
        self.holding.sold_at = 9500
        self.holding.save()

        self.assertAlmostEqual(self.holding.value, 60.80)
        self.assertAlmostEqual(self.holding.profit_loss, -3.20)
        self.assertAlmostEqual(self.holding.growth_rate, -5.0)


    def test__aer__one_year(self) -> None:
        """Returns the annual equivalent rate of the profit or loss."""

        self.holding.bought_on = timezone.now().date() - timedelta(365)
        self.holding.save()

        self.assertAlmostEqual(self.holding.profit_loss, 3.20)
        self.assertAlmostEqual(self.holding.growth_rate, 5.0)
        self.assertAlmostEqual(self.holding.growth_aer, 5.0)


    def test__aer__two_years(self) -> None:
        """Returns the annual equivalent rate of the profit or loss."""

        self.holding.bought_on = timezone.now().date() - timedelta(2 * 365)
        self.holding.save()

        self.assertAlmostEqual(self.holding.profit_loss, 3.20)
        self.assertAlmostEqual(self.holding.growth_rate, 5.0)
        self.assertAlmostEqual(self.holding.growth_aer, 2.4695, places=4)


    def test__aer__three_months(self) -> None:
        """Returns the annual equivalent rate of the profit or loss."""

        self.holding.bought_on = timezone.now().date() - timedelta(91)
        self.holding.save()

        self.assertAlmostEqual(self.holding.profit_loss, 3.20)
        self.assertAlmostEqual(self.holding.growth_rate, 5.0)
        self.assertAlmostEqual(self.holding.growth_aer, 21.6158, places=4)


    def test__sell__full_sale(self) -> None:
        """Sells the entire holding today."""

        profit_loss = self.holding.sell()

        self.assertEqual(self.fund.holdings.count(), 1)
        self.assertEqual(self.holding.quantity, 64)
        self.assertEqual(self.holding.sold_on, timezone.now().date())
        self.assertAlmostEqual(profit_loss, 3.20)


    def test__sell__explicit_full_sale(self) -> None:
        """Sells the entire holding today."""

        profit_loss = self.holding.sell(quantity=64)

        self.assertEqual(self.fund.holdings.count(), 1)
        self.assertEqual(self.holding.quantity, 64)
        self.assertEqual(self.holding.sold_on, timezone.now().date())
        self.assertAlmostEqual(profit_loss, 3.20)


    def test__sell__partial_sale(self) -> None:
        """Sells part of the holding today."""

        profit_loss = self.holding.sell(quantity=48)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.assertEqual(self.holding.quantity, 48)
        self.assertEqual(self.holding.sold_on, timezone.now().date())
        self.assertAlmostEqual(profit_loss, 2.40)

        continuation = exists(self.fund.holdings.last())
        self.assertEqual(continuation.quantity, 16)
        self.assertEqual(continuation.bought_on, date(2024, 4, 6))
        self.assertEqual(continuation.bought_at, 10000)


    def test__sell__zero_quantity(self) -> None:
        """Throws an error and no changes are made."""

        with self.assertRaises(AssertionError):
            self.holding.sell(quantity=0)

        self.assertEqual(self.fund.holdings.count(), 1)
        self.assertEqual(self.holding.quantity, 64)
        self.assertIsNone(self.holding.sold_on)


    def test__sell__negative_quantity(self) -> None:
        """Throws an error and no changes are made."""

        with self.assertRaises(AssertionError):
            self.holding.sell(quantity=-48)

        self.assertEqual(self.fund.holdings.count(), 1)
        self.assertEqual(self.holding.quantity, 64)
        self.assertIsNone(self.holding.sold_on)


    def test__sell__overselling(self) -> None:
        """Throws an error and no changes are made."""

        with self.assertRaises(AssertionError):
            self.holding.sell(quantity=-48)

        self.assertEqual(self.fund.holdings.count(), 1)
        self.assertEqual(self.holding.quantity, 64)
        self.assertIsNone(self.holding.sold_on)


    def test__sell__yesterday(self) -> None:
        """Records the sale date provided, and uses the most recent historical price point."""

        yesterday = timezone.now().date() - timedelta(1)
        profit_loss = self.holding.sell(date=yesterday)

        self.assertEqual(self.holding.sold_on, yesterday)
        self.assertAlmostEqual(profit_loss, 1.92)


    def test__sell__before_buy(self) -> None:
        """Throws an error if the sale happens before the buy."""

        with self.assertRaises(AssertionError):
            self.holding.sell(date=self.holding.bought_on - timedelta(1))

        self.assertIsNone(self.holding.sold_on)


    def test__sell__tomorrow(self) -> None:
        """Throws an error if the sale happens in the future."""

        with self.assertRaises(AssertionError):
            self.holding.sell(date=timezone.now().date() + timedelta(1))

        self.assertIsNone(self.holding.sold_on)


class Test__AER(TestCase):

    def test__no_holdings(self) -> None:
        """Does not error if no holdings are supplied"""

        self.assertEqual(calculate_aer([]), 0)


    def test__various_holdings(self) -> None:
        """Calculates an approximate AER for a variety of holdings & growth rates"""

        date_ref = date.fromisoformat('2025-03-25')
        fund = Fund.objects.create()
        portfolio = Portfolio.objects.create()
        fund.price_points.create(
            date = date_ref + timedelta(91),
            hundredths = 12500,
        )

        holdings = [
            fund.holdings.create(
                portfolio=portfolio,
                quantity=1,
                bought_on=date_ref - timedelta(365),
                bought_at=10000,
                sold_on=date_ref,
                sold_at=11000,
            ),
            fund.holdings.create(
                portfolio=portfolio,
                quantity=2,
                bought_on=date_ref - timedelta(365),
                bought_at=10000,
                sold_on=date_ref,
                sold_at=15000,
            ),
            fund.holdings.create(
                portfolio=portfolio,
                quantity=5,
                bought_on=date_ref - timedelta(182),
                bought_at=10000,
            ),
            fund.holdings.create(
                portfolio=portfolio,
                quantity=2.5,
                bought_on=date_ref,
                bought_at=12000,
            ),
        ]

        self.assertAlmostEqual(calculate_aer(holdings), 0.3407, 4)


class Test_Tags(TestCase):

    def test__is_todays_price__standard_weekday_before_deadline(self) -> None:
        """Flags a weekday price after 17:00 the following working day."""

        wednesday = date(2026, 8, 26)
        deadline = datetime.combine(
            wednesday + timedelta(days=1),
            time(17, 0),
            timezone.get_current_timezone(),
        )
        current_time = deadline - timedelta(seconds = 1)

        with patch('invest.templatetags.invest_tags.timezone.now', return_value=current_time):
            self.assertEqual(is_todays_price(wednesday), '')


    def test__is_todays_price__standard_weekday_after_deadline(self) -> None:
        """Flags a weekday price after 17:00 the following working day."""

        wednesday = date(2026, 8, 26)
        deadline = datetime.combine(
            wednesday + timedelta(days=1),
            time(17, 0),
            timezone.get_current_timezone(),
        )

        with patch('invest.templatetags.invest_tags.timezone.now', return_value=deadline):
            self.assertIn('🕔', is_todays_price(wednesday))


    def test__is_todays_price__weekend_saturday(self) -> None:
        """Does not flag Friday prices as dated on the weekend or before Monday 17:00."""

        friday = date(2026, 8, 28)
        deadline = datetime.combine(
            friday + timedelta(days=3),
            time(17, 0),
            timezone.get_current_timezone(),
        )
        current_time = deadline - timedelta(days=2)

        with patch('invest.templatetags.invest_tags.timezone.now', return_value=current_time):
            self.assertEqual(is_todays_price(friday), '')


    def test__is_todays_price__weekend_sunday(self) -> None:
        """Does not flag Friday prices as dated on the weekend or before Monday 17:00."""

        friday = date(2026, 8, 28)
        deadline = datetime.combine(
            friday + timedelta(days=3),
            time(17, 0),
            timezone.get_current_timezone(),
        )
        current_time = deadline - timedelta(days=1)

        with patch('invest.templatetags.invest_tags.timezone.now', return_value=current_time):
            self.assertEqual(is_todays_price(friday), '')


    def test__is_todays_price__weekend_monday_before_deadline(self) -> None:
        """Does not flag Friday prices as dated on the weekend or before Monday 17:00."""

        friday = date(2026, 8, 28)
        deadline = datetime.combine(
            friday + timedelta(days=3),
            time(17, 0),
            timezone.get_current_timezone(),
        )
        current_time = deadline - timedelta(seconds=1)

        with patch('invest.templatetags.invest_tags.timezone.now', return_value=current_time):
            self.assertEqual(is_todays_price(friday), '')


    def test__is_todays_price__weekend_monday_after_deadline(self) -> None:
        """Does not flag Friday prices as dated on the weekend or before Monday 17:00."""

        friday = date(2026, 8, 28)
        deadline = datetime.combine(
            friday + timedelta(days=3),
            time(17, 0),
            timezone.get_current_timezone(),
        )

        with patch('invest.templatetags.invest_tags.timezone.now', return_value=deadline):
            self.assertIn('🕔', is_todays_price(friday))

