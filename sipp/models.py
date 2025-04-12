from django.db import models  # noqa: F401
from django.utils.functional import cached_property


class Fund(models.Model):

    short_name = models.CharField(max_length=255)
    full_name = models.TextField(max_length=255)
    tag = models.CharField(max_length=255)

    bought_on = models.DateField()
    bought_price = models.IntegerField()  # In hundredths of a pence
    bought_quantity = models.FloatField()

    url = models.URLField(max_length=255)

    def __str__(self) -> str:
        return f'{self.short_name} ({self.tag})'


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

