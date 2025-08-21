from django.db import models, transaction
from library.models import Library
from django.utils import timezone
from datetime import timedelta


# Create your models here.
class BookInfo(models.Model):
    #pk
    isbn = models.CharField(
        primary_key=True,
        max_length=13,
    )

    title = models.CharField("제목", max_length=255)
    author = models.CharField("저자", max_length=255, blank=True)
    publisher = models.CharField("출판사", max_length=255, blank=True)
    published_date = models.DateField("출간일", null=True, blank=True)

    cover_url = models.URLField("표지 이미지", max_length=500, blank=True)
    category = models.CharField("카테고리", max_length=50, blank=True)  # 태그화 예정이면 M2M로 분리 가능
    regular_price = models.IntegerField("정가", null=True, blank=True)
    sale_price = models.IntegerField("정가", null=True, blank=True)

    description = models.TextField("설명", blank=True)
    vector = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "BookInfo"
        verbose_name = "책 메타"
        verbose_name_plural = "책 메타"
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["author"]),
            models.Index(fields=["publisher"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.isbn})"
    
class BookInfoLibrary(models.Model):
    """
    테이블이 처음 생성될 때 median_date는 expired_date와 created_at의 중간일
    이후에는 user-book모델의 created날과 기존 median_date의 중간 날짜로 업데이트

    expired_at은 median_date로 부터 30일 이후로 설정
    """
    STATUS = [
        ("AVAILABLE", "구매가능"),
        ("PICKED", "구매불가"),
        ("EXPIRED", "만료"),
    ]

    library_id = models.ForeignKey(
        Library, to_field="id", on_delete=models.CASCADE,
        related_name="bookinfo", db_column="library_id"
    )

    isbn = models.ForeignKey(
        BookInfo, to_field="isbn", on_delete=models.CASCADE,
        related_name="bookinfo", db_column="isbn"
    )

    quantity = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS, default="AVAILABLE") # 상태
    median_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # 같은 도서관-ISBN 조합은 한 행만 유지하고 싶다면 권장
        constraints = [
            models.UniqueConstraint(fields=['library_id', 'isbn'], name='uniq_library_isbn_bil')
        ]

    def _midpoint(self, a, b):
        """두 datetime의 중간값 반환 (tz 보존)"""
        if a > b:
            a, b = b, a
        delta = b - a
        return a + (delta / 2)

    def save(self, *args, **kwargs):
        # 최초 생성 시에만 기본값 세팅
        if self.pk is None:
            now = timezone.now()
            # created_at은 auto_now_add지만 계산상 필요하므로 기준 시각을 now로 사용
            base_created = self.created_at or now

            # 최초 median_date 가이드:
            # created_at ~ (created_at + 30일)의 중간 = created_at + 15일
            if self.median_date is None:
                self.median_date = base_created + timedelta(days=15)

            # expired_at = median_date + 30일
            if self.expired_at is None:
                self.expired_at = self.created_at + timedelta(days=30)

        super().save(*args, **kwargs)
    
    @transaction.atomic
    def update_median_with(self, userbook_created_at, *, save=True):
        """
        UserBook이 생성될 때 호출:
        - median_date = (기존 median_date, userbook_created_at) 의 중간일
        - expired_at  = median_date + 30일
        """
        if userbook_created_at is None:
            return  # 방어적

        # 기존 median_date가 없다면 초기화 로직과 동일 처리
        if self.median_date is None:
            self.median_date = userbook_created_at
        else:
            self.median_date = self._midpoint(self.median_date, userbook_created_at)

        self.expired_at = self.median_date + timedelta(days=30)

        if save:
            self.save(update_fields=["median_date", "expired_at", "updated_at"])
