from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from bookinfo.models import BookInfo
from library.models import Library

class Book(models.Model):
    STATUS = [
        ("AVAILABLE", "구매가능"),
        ("PICKED", "구매불가"),
        ("EXPIRED", "만료"),
    ]
    
    # pk
    id = models.BigAutoField(primary_key=True)

    library = models.ForeignKey(
        Library, on_delete=models.CASCADE, related_name="books",
        db_column="library_id"
    )
    
    isbn = models.ForeignKey(
        BookInfo, to_field="isbn", on_delete=models.PROTECT,
        related_name="books", db_column="isbn"
    )

    expire_date = models.DateTimeField(null=True, blank=True) # 기증일로부터 30일 후
    standard_price = models.IntegerField(null=True, blank=True) # 정가
    donation_date = models.DateTimeField(auto_now_add=True) # 기증일
    status = models.CharField(max_length=20, choices=STATUS, default="AVAILABLE") # 상태

    donor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="donated_books",
        db_column="donor_user_id"
    )

    class Meta:
        db_table = "Book"
        indexes = [
            models.Index(fields=["library", "status"]),
            models.Index(fields=["library", "isbn", "status"]),
        ]

    def save(self, *args, **kwargs):
        # 새로 생성될 때만 만료일 설정
        if not self.pk and not self.expire_date:
            self.expire_date = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.isbn_id} @ {self.library_id} [{self.status}]"
