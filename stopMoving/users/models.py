from django.db import models
from accounts.models import User
from books.models import Book

# Create your models here.
class UserInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    preference_keyword = models.JSONField(null=True, blank=True)
    preference_vector = models.JSONField(null=True, blank=True)
    points = models.BigIntegerField(default=0)

class Status(models.TextChoices):
    DONATED = 'DONATED', '기증'
    PURCHASED = 'PURCHASED', '구매'

class UserBook(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    book = models.OneToOneField(Book, on_delete=models.PROTECT)
    status = models.CharField( # 상태: 기증/구매
        max_length=20,
        choices=Status.choices,   # Enum 연결
    )

    class Meat:
        unique_together = {'users', 'book'}