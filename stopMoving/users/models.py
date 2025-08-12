from django.db import models
from accounts.models import User
from books.models import Book
from django.conf import settings

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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="user_books",
        db_column="user_id",
    )
    book = models.ForeignKey(
        'books.Book',
        on_delete=models.CASCADE,  
        db_column='book_id',
        null=False, 
        blank=False,
    )
    status = models.CharField( # 상태: 기증/구매
        max_length=20,
        choices=Status.choices,   # Enum 연결
    )

    class Meta:
        unique_together = (('user', 'book'),)
      

