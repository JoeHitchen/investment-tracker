from django.urls import path, include

from . import views


app_name = 'sipp'

urlpatterns = [
    path('portfolio/<str:portfolio>/', include([
        path(
            'total-value/',
            views.PortfolioGraphView.as_view(),
            name = 'graph-total-value',
            kwargs = {'profit_loss': False},
        ),
        path(
            'profit-loss/',
            views.PortfolioGraphView.as_view(),
            name = 'graph-profit-loss',
            kwargs = {'profit_loss': True},
        ),
    ])),
    path('', views.IndexView.as_view(), name = 'index'),
]

