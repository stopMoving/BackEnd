from django.contrib import admin
from .models import BookInfo

@admin.register(BookInfo)
class BookInfoAdmin(admin.ModelAdmin):
    list_display = ("isbn", "title", "author", "publisher", "category", "regular_price")
    search_fields = ("isbn", "title", "author", "publisher")
    list_filter = ("publisher", "category")