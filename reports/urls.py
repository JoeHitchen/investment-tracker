from django.urls import path

from . import views


app_name = 'reports'

urlpatterns = [
    path('isa-report/', views.IsaReport.as_view(), name = 'isa'),
]
