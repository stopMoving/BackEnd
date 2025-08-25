# notifications/urls.py
from django.urls import path
from .views import NotificationListView, NotificationUnreadCountView

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"), # GET: 최근 30일
    path("unread-count/", NotificationUnreadCountView.as_view(), name="unread-count"),
]
