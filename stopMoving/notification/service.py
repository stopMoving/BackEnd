# notifications/service.py
from .models import Notification

def push(user, type_, title, message="", data=None):
    Notification.objects.create(
        user=user,
        type=type_,
        message=message or "",
    )
