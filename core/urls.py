from django.urls import path, include

urlpatterns = [
    path('', include('invest.urls')),
    path('', lambda req: None, name = 'index'),  # type: ignore # Root URL alias, handled by app
]

