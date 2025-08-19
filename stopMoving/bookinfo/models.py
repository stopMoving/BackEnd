from django.db import models

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