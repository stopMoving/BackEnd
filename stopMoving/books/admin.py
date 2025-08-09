from django.contrib import admin
from .models import Book

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "id", "isbn", "get_title", "library", "donor_user",
        "status", "donation_date", "expire_date", "current_price"
    )
    list_filter = ("status", "library", "donation_date", "expire_date")
    search_fields = ("isbn__isbn", "isbn__name", "library__name", "donor_user__username")
    ordering = ("-donation_date",) # 기증날 기준 정렬

    # 책 제목을 ForeignKey(BookInfo)에서 가져오기
    def get_title(self, obj):
        return obj.isbn.name
    get_title.short_description = "제목"
