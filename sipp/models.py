from datetime import date

from django.db import models, transaction
from django.utils.functional import cached_property
from django.utils import timezone

from .utils import exists


class Fund(models.Model):

    short_name = models.CharField(max_length=255)
    full_name = models.TextField(max_length=255)
    tag = models.CharField(max_length=255)

    url = models.URLField(max_length=255)
    monitor_price = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f'{self.short_name} ({self.tag})'

    @transaction.atomic
    def sell(self, quantity: float, date: date | None = None) -> float:
        """Records the sale of fund holdings on the given date, defaulting to today.

        Funds are sold in age order, with the oldest holdings sold first.
        """
        assert quantity > 0
        if date is None:
            date = timezone.now().date()

        profit_loss = 0.0
        for holding in self.holdings.filter(sold_on__isnull=True).order_by('bought_on'):
            if quantity <= holding.quantity:
                profit_loss += holding.sell(quantity, date)
                break

            profit_loss += holding.sell(date = date)
            quantity -= holding.quantity
        else:
            raise AssertionError('Attempting to sell more units than are held')

        return profit_loss


class Holding(models.Model):

    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name='holdings')
    quantity = models.FloatField()

    bought_on = models.DateField()
    bought_at = models.IntegerField()  # In hundredths of a pence
    sold_on = models.DateField(null=True)
    sold_at = models.IntegerField(null=True)  # In hundredths of a pence

    class Meta:
        ordering = ['fund', 'bought_on', '-quantity']

    @cached_property
    def profit_loss(self) -> float:
        """Returns the total profit or loss on the holding, in pounds.

        Uses the sale price for closed holdings, or the latest price point for current holdings.
        """
        if self.sold_at is None:
            end_price = exists(self.fund.price_points.last()).hundredths
        else:
            end_price = self.sold_at
        return (end_price - self.bought_at) * self.quantity / 10000


    @transaction.atomic
    def sell(self, quantity: float | None = None, date: date | None = None) -> float:
        """Records the sale of the holding on the given date, defaulting to today.

        Partial sales are handled by creating a new holding with the remaining quantity.
        """

        assert quantity is None or 0 < quantity <= self.quantity
        if quantity and quantity < self.quantity:
            self.fund.holdings.create(
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

