from datetime import date, timedelta

from django.test import TestCase
from django.db.models import QuerySet
from django.utils import timezone

from sipp.models import Fund, Holding, PricePoint
from sipp.utils import exists


class Test_Fund(TestCase):

    fund: Fund
    holding_1: Holding
    holding_2: Holding
    other_holdings: QuerySet[Holding]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.fund = Fund.objects.create()
        cls.holding_1 = cls.fund.holdings.create(
            quantity=64,
            bought_on=date(2024, 4, 6),
            bought_at=10000,
        )
        cls.holding_2 = cls.fund.holdings.create(
            quantity=32,
            bought_on=date(2024, 4, 10),
            bought_at=11000,
        )
        cls.fund.price_points.create(date=date(2024, 4, 6), hundredths=10000)
        cls.fund.price_points.create(date=date(2024, 4, 10), hundredths=11000)
        cls.fund.price_points.create(date=date(2024, 10, 5), hundredths=12000)
        holding_ids = [cls.holding_1.id, cls.holding_2.id]
        cls.other_holdings = cls.fund.holdings.exclude(id__in = holding_ids)


    def test__buy__purchase_today(self) -> None:
        """Creates a new holding on the given date, defaulting to today."""

        self.fund.buy(quantity=100)
        self.assertEqual(self.fund.holdings.count(), 3)

        new_holding = exists(self.other_holdings.last())
        self.assertEqual(new_holding.quantity, 100)
        self.assertEqual(new_holding.bought_on, timezone.now().date())
        self.assertEqual(new_holding.bought_at, 12000)
        self.assertIsNone(new_holding.sold_on)
        self.assertIsNone(new_holding.sold_at)


    def test__buy__purchase_historical(self) -> None:
        """Creates a new holding on the given date, defaulting to today."""

        self.fund.buy(quantity=100, date=date(2024, 7, 5))
        self.assertEqual(self.fund.holdings.count(), 3)

        new_holding = exists(self.other_holdings.last())
        self.assertEqual(new_holding.quantity, 100)
        self.assertEqual(new_holding.bought_on, date(2024, 7, 5))
        self.assertEqual(new_holding.bought_at, 11000)
        self.assertIsNone(new_holding.sold_on)
        self.assertIsNone(new_holding.sold_at)


    def test__buy__zero_quantity(self) -> None:
        """Raises an error if the purchase is for zero units."""

        with self.assertRaises(AssertionError):
            self.fund.buy(quantity=0)
        self.assertEqual(self.fund.holdings.count(), 2)


    def test__buy__negative_quantity(self) -> None:
        """Raises an error if the purchase is for a negative number of units."""

        with self.assertRaises(AssertionError):
            self.fund.buy(quantity=-1)
        self.assertEqual(self.fund.holdings.count(), 2)


    def test__sell__full_first_holding(self) -> None:
        """Sells all of the first holding."""

        profit_loss = self.fund.sell(quantity=64)
        self.assertEqual(profit_loss, 12.80)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertEqual(self.holding_1.sold_on, timezone.now().date())

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertIsNone(self.holding_2.sold_on)


    def test__sell__partial_first_holding(self) -> None:
        """Sells part of the first holding."""

        profit_loss = self.fund.sell(quantity=27)
        self.assertEqual(profit_loss, 5.40)

        self.assertEqual(self.fund.holdings.count(), 3)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 27)
        self.assertEqual(self.holding_1.sold_on, timezone.now().date())

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

        profit_loss = self.fund.sell(quantity=96)
        self.assertEqual(profit_loss, 16.00)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertEqual(self.holding_1.sold_on, timezone.now().date())

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertEqual(self.holding_2.sold_on, timezone.now().date())


    def test__sell__partial_second_holding(self) -> None:
        """Sells all of the first holding and part of the second holding."""

        profit_loss = self.fund.sell(quantity=71)
        self.assertEqual(profit_loss, 13.5)

        self.assertEqual(self.fund.holdings.count(), 3)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertEqual(self.holding_1.sold_on, timezone.now().date())

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 7)
        self.assertEqual(self.holding_2.sold_on, timezone.now().date())

        new_holding = exists(self.other_holdings.last())
        self.assertEqual(new_holding.quantity, 25)
        self.assertEqual(new_holding.bought_on, self.holding_2.bought_on)
        self.assertEqual(new_holding.bought_at, self.holding_2.bought_at)
        self.assertIsNone(new_holding.sold_on)
        self.assertIsNone(new_holding.sold_at)


    def test__sell__oversale(self) -> None:
        """Raises an error if the sale is for more units than are held."""

        with self.assertRaises(AssertionError):
            self.fund.sell(quantity=128)

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
            self.fund.sell(quantity=0)

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
            self.fund.sell(quantity=-1)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.holding_1.refresh_from_db()
        self.assertEqual(self.holding_1.quantity, 64)
        self.assertIsNone(self.holding_1.sold_on)

        self.holding_2.refresh_from_db()
        self.assertEqual(self.holding_2.quantity, 32)
        self.assertIsNone(self.holding_2.sold_on)


    def test__sell__yesterday(self) -> None:
        """Records the sale of both holdings against the date provided."""

        profit_loss = self.fund.sell(quantity=96, date=timezone.now().date() - timedelta(5))
        self.assertEqual(profit_loss, 16.00)

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
            self.fund.sell(quantity=96, date=timezone.now().date() + timedelta(1))

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
            quantity=64,
            bought_on=date(2024, 4, 6),
            bought_at=10000,
        )
        cls.fund.price_points.create(date=date(2025, 4, 5), hundredths=10300)
        cls.latest_price = cls.fund.price_points.create(
            date=timezone.now().date(),
            hundredths=10500,
        )


    def test__profit_loss__still_held_at_profit(self) -> None:
        """Uses the latest price point multiplied by the quantity."""

        self.assertEqual(self.holding.profit_loss, 3.20)


    def test__profit_loss__still_held_at_loss(self) -> None:
        """Uses the latest price point multiplied by the quantity."""

        self.latest_price.hundredths = 9500
        self.latest_price.save()

        self.assertEqual(self.holding.profit_loss, -3.20)


    def test__profit_loss__sold_at_profit(self) -> None:
        """Uses the sale price provided multiplied by the quantity."""

        self.holding.sold_on = date(2025, 4, 5)
        self.holding.sold_at = 10700
        self.holding.save()

        self.assertEqual(self.holding.profit_loss, 4.48)


    def test__profit_loss__sold_at_loss(self) -> None:
        """Uses the sale price provided."""

        self.holding.sold_on = date(2025, 4, 5)
        self.holding.sold_at = 9500
        self.holding.save()

        self.assertEqual(self.holding.profit_loss, -3.20)


    def test__sell__full_sale(self) -> None:
        """Sells the entire holding today."""

        profit_loss = self.holding.sell()

        self.assertEqual(self.fund.holdings.count(), 1)
        self.assertEqual(self.holding.quantity, 64)
        self.assertEqual(self.holding.sold_on, timezone.now().date())
        self.assertEqual(profit_loss, 3.20)


    def test__sell__explicit_full_sale(self) -> None:
        """Sells the entire holding today."""

        profit_loss = self.holding.sell(quantity=64)

        self.assertEqual(self.fund.holdings.count(), 1)
        self.assertEqual(self.holding.quantity, 64)
        self.assertEqual(self.holding.sold_on, timezone.now().date())
        self.assertEqual(profit_loss, 3.20)


    def test__sell__partial_sale(self) -> None:
        """Sells part of the holding today."""

        profit_loss = self.holding.sell(quantity=48)

        self.assertEqual(self.fund.holdings.count(), 2)
        self.assertEqual(self.holding.quantity, 48)
        self.assertEqual(self.holding.sold_on, timezone.now().date())
        self.assertEqual(profit_loss, 2.40)

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
        self.assertEqual(profit_loss, 1.92)


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

