from django.contrib import admin
from .models import UserInfo, UserBook

# Register your models here.
@admin.register(UserInfo)
class UserInfoAdmin(admin.ModelAdmin):
    list_display = ("user", "preference_keyword", "preference_vector", "points")
    search_fields = ("user__username",)
    list_filter = ("user__username",)

@admin.register(UserBook)
class UserBookAdmin(admin.ModelAdmin):
    list_display = ("user", "status")
    search_fields = ("user__username",)
    list_filter = ("status",)