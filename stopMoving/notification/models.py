from django.db import models
from users.models import User
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('book_recommendation', '추천'),
        ('book_donated', '책 나눔'),
        ('book_pickup', '책 가져가기'),
    ]
    # id는 pk
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification')
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["type", "-created_at"]),
        ]
        ordering = ['-created_at']