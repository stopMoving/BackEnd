# notifications/urls.py
from django.urls import path
from .views import NotificationListView

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"), # GET: 최근 30일
]
