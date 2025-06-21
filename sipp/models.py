from datetime import date
from math import pow as power
from typing import Iterable, cast

from django.db import models, transaction
from django.utils.functional import cached_property
from django.utils import timezone
import pyxirr

from .utils import exists


class Portfolio(models.Model):

    class Types(models.TextChoices):
        SIPP = 'SIPP', 'SIPP'
        ISA = 'ISA', 'ISA'

    type = models.CharField(max_length=4, choices=Types.choices)

    _active_holdings: list['Holding']  # Used for prefetching

    def __str__(self) -> str:
        return self.type

    def active_holdings(self) -> Iterable['Holding']:
        """Returns the active holdings for the portfolio, using a cache if provided."""

        if hasattr(self, '_active_holdings') and len(self._active_holdings):
            return self._active_holdings
        else:
            return self.holdings.filter(sold_on__isnull=True)

    @cached_property
    def total_cost(self) -> float:
        """Returns the total cost of the active holdings."""
        return sum(holding.cost for holding in self.active_holdings())

    @cached_property
    def total_value(self) -> float:
        """Returns the total value of the active holdings."""
        return sum(holding.value for holding in self.active_holdings())

    @cached_property
    def total_profit_loss(self) -> float:
        """Returns the total profit or loss of the active holdings."""
        return self.total_value - self.total_cost

    @cached_property
    def growth_rate(self) -> float:
        """Returns the overall growth rate of the active holdings."""
        return 100 * self.total_profit_loss / self.total_cost

    @cached_property
    def growth_aer(self) -> float:
        """Returns an approximate Annual Equivalent Rate (AER) for the active portfolio."""

        dates = []
        purchases = []
        for holding in self.active_holdings():
            dates.append(holding.bought_on)
            purchases.append(holding.cost)

        dates.append(timezone.now().date())
        purchases.append(-self.total_value)
        return 100 * exists(pyxirr.xirr(dates, purchases))


class Fund(models.Model):

    short_name = models.CharField(max_length=255)
    full_name = models.TextField(max_length=255)
    tag = models.CharField(max_length=255)

    url = models.URLField(max_length=255)
    monitor_price = models.BooleanField(default=True)

    _latest_price_points: list['PricePoint']  # Used for prefetching

    def __str__(self) -> str:
        return f'{self.short_name} ({self.tag})'


    @cached_property
    def latest_price_point(self) -> 'PricePoint':
        """Returns the latest price point for the holding, using a cache if provided."""

        if hasattr(self, '_latest_price_points') and len(self._latest_price_points):
            return self._latest_price_points[0]
        return exists(self.price_points.all().last())


    def buy(self, portfolio: Portfolio | str, quantity: float, date: date | None = None) -> float:
        """Records the purchase of the holding on the given date, defaulting to today."""

        if type(portfolio) is str:
            portfolio = Portfolio.objects.get(type = portfolio)
        portfolio = cast(Portfolio, portfolio)
        assert portfolio.type in Portfolio.Types, f'{portfolio} is not a recognised portfolio'

        assert quantity > 0
        assert date is None or (date <= timezone.now().date())
        if date is None:
            date = timezone.now().date()

        new_holding = self.holdings.create(
            portfolio=portfolio,
            quantity=quantity,
            bought_on=date,
            bought_at=exists(self.price_points.filter(date__lte=date).last()).hundredths,
        )
        return new_holding.cost


    @transaction.atomic
    def sell(self, portfolio: Portfolio | str, quantity: float, date: date | None = None) -> float:
        """Records the sale of fund holdings on the given date, defaulting to today.

        Funds are sold in age order, with the oldest holdings sold first.
        """

        if type(portfolio) is str:
            portfolio = Portfolio.objects.get(type = portfolio)
        portfolio = cast(Portfolio, portfolio)
        assert portfolio.type in Portfolio.Types, f'{portfolio} is not a recognised portfolio'

        assert quantity > 0
        if date is None:
            date = timezone.now().date()

        profit_loss = 0.0
        holdings = self.holdings.filter(portfolio=portfolio, sold_on__isnull=True)
        for holding in holdings.order_by('bought_on'):
            if quantity <= holding.quantity:
                profit_loss += holding.sell(quantity, date)
                break

            profit_loss += holding.sell(date = date)
            quantity -= holding.quantity
        else:
            raise AssertionError('Attempting to sell more units than are held')

        return profit_loss


class Holding(models.Model):

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='holdings')
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name='holdings')
    quantity = models.FloatField()

    bought_on = models.DateField()
    bought_at = models.IntegerField()  # In hundredths of a pence
    sold_on = models.DateField(null=True)
    sold_at = models.IntegerField(null=True)  # In hundredths of a pence

    _latest_price_points: list['PricePoint']  # Used for prefetching

    class Meta:
        ordering = ['fund', 'bought_on', '-quantity']


    @cached_property
    def cost(self) -> float:
        """Returns the original cost of the holding, in pounds."""
        return self.bought_at * self.quantity / 10000


    @cached_property
    def end_price(self) -> float:
        """Returns the final or current price of the holding, in pounds."""

        if self.sold_at:
            end_price = self.sold_at
        elif hasattr(self, '_latest_price_points') and len(self._latest_price_points):
            end_price = self._latest_price_points[0].hundredths
        else:
            end_price = exists(self.fund.price_points.last()).hundredths

        return end_price / 10000


    @cached_property
    def value(self) -> float:
        """Returns the current or final value of the holding, in pounds."""
        return self.end_price * self.quantity


    @cached_property
    def profit_loss(self) -> float:
        """Returns the total profit or loss on the holding, in pounds.

        Uses the sale price for closed holdings, or the latest price point for current holdings.
        """
        return self.value - self.cost


    @cached_property
    def growth_rate(self) -> float:
        """Returns the growth rate of an investment as a percentage.

        Uses the sale price for closed holdings, or the latest price point for current holdings.
        """
        return self.profit_loss / self.cost * 100


    @cached_property
    def growth_aer(self) -> float:
        """Returns the growth rate of the holding, as an annual equivalent rate.

        Uses the sale price for closed holdings, or the latest price point for current holdings.
        """

        end_date = self.sold_on if self.sold_on else timezone.now().date()
        profit_loss_multiplier = (1 + self.growth_rate / 100)

        return 100 * (power(profit_loss_multiplier, (365 / (end_date - self.bought_on).days)) - 1)


    @transaction.atomic
    def sell(self, quantity: float | None = None, date: date | None = None) -> float:
        """Records the sale of the holding on the given date, defaulting to today.

        Partial sales are handled by creating a new holding with the remaining quantity.
        """

        assert quantity is None or 0 < quantity <= self.quantity
        if quantity and quantity < self.quantity:
            self.fund.holdings.create(
                portfolio=self.portfolio,
                quantity=self.quantity - quantity,
                bought_on=self.bought_on,
                bought_at=self.bought_at,
            )
            self.quantity = quantity

        assert date is None or (self.bought_on <= date <= timezone.now().date())
        self.sold_on = date if date else timezone.now().date()

        sold_price_point = self.fund.price_points.filter(date__lte=self.sold_on).last()
        self.sold_at = exists(sold_price_point).hundredths
        self.save()

        self.profit_loss; del self.profit_loss  # noqa: E702
        return self.profit_loss


class PricePoint(models.Model):

    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name='price_points')
    date = models.DateField()
    hundredths = models.IntegerField()  # Fund price in hundredths of a pence

    def __str__(self) -> str:
        return f'{self.fund.tag} ({self.date}) {self.pence}p'

    class Meta:
        db_table = 'sipp_price_point'
        unique_together = ('fund', 'date')
        ordering = ['fund', 'date']

    @cached_property
    def pence(self) -> float:
        return self.hundredths / 100

    @cached_property
    def pounds(self) -> float:
        return self.pence / 100

