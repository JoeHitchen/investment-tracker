from django.urls import path, include

from . import views


app_name = 'sipp'

urlpatterns = [
    path('portfolio/<str:portfolio>/', include([
        path('', views.PortfolioGraphView.as_view(), name = 'graphs'),
    ])),
    path('', views.IndexView.as_view(), name = 'index'),
]

