from django.contrib import admin
from .models import Library

# Register your models here.
@admin.register(Library)
class BookInfoAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "contact", "closed_days", "hours_of_use", "sns", "lat", "long")
    search_fields = ("name",)
    list_filter = ("name",)