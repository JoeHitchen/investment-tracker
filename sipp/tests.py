from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from sipp.models import Fund, Holding, PricePoint
from sipp.utils import exists


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

