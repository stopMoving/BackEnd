from django.urls import path
from .views import Ping

urlpatterns = [
    path('ping/', Ping.as_view(), name='ping'),
]
