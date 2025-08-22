from django.db import models
from accounts.models import User
from books.models import Book
from django.conf import settings
from bookinfo.models import BookInfo

# Create your models here.
class UserInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    preference_keyword = models.JSONField(null=True, blank=True)
    preference_vector = models.JSONField(null=True, blank=True) # 통합
    preference_vector_survey = models.JSONField(null=True, blank=True)
    preference_vector_activity = models.JSONField(null=True, blank=True)
    survey_done = models.BooleanField(default=False)
    last_survey_at = models.DateTimeField(blank=True, null=True)
    points = models.BigIntegerField(default=0)
    my_lib_ids = models.JSONField(default=list, blank=True)  # 내 도서관 id들을 리스트로 저장
    preference_book = models.JSONField(default=list, blank=True) # 선호 책 추천 목록 (1~5등)

    updated_at = models.DateTimeField(auto_now=True)


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
    bookinfo = models.ForeignKey(
        BookInfo,
        to_field='isbn',              # ← BookInfo.isbn이 PK 또는 UNIQUE 여야 함
        on_delete=models.PROTECT,
        related_name='userbook_links',
        related_query_name='userbook',
        db_column='isbn',
    )
    status = models.CharField( # 상태: 기증/구매
        max_length=20,
        choices=Status.choices,   # Enum 연결
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True) # 사실상 bookinfo-library의 updated_at

    quantity = models.IntegerField(default=0)

    library_id = models.IntegerField(null=True)

    class Meta:
        #unique_together = (('user', 'bookinfo', 'status'),) # 기증한 책을 기증자가 못가져감 -> 삭제 시 기증자가 기증한 책 가져갈 수 있음
        
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["bookinfo", "status"]),
        ]
      

