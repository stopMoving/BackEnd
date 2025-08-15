# appname/admin.py
from django.contrib import admin
from .models import LibraryBookStock, BookReservation, ReservationStatus

@admin.register(LibraryBookStock)
class LibraryBookStockAdmin(admin.ModelAdmin):
    list_display = ('library', 'isbn', 'available_count', 'total_count')
    list_filter = ('library',)
    search_fields = ('library__name', 'isbn__title', 'isbn__isbn')

@admin.register(BookReservation)
class BookReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'book_stock', 'quantity', 'status', 'reserved_at', 'expires_at')
    list_filter = ('status', 'reserved_at', 'expires_at')
    search_fields = ('user__username', 'book_stock__isbn__title', 'book_stock__library__name')
    actions = ['mark_expired']

    @admin.action(description="선택 항목 만료 처리(재고 복구)")
    def mark_expired(self, request, queryset):
        from django.db.models import F
        qs = queryset.filter(status=ReservationStatus.ACTIVE)
        for r in qs:
            LibraryBookStock.objects.filter(pk=r.book_stock_id)\
                                    .update(available_count=F('available_count') + r.quantity)
        qs.update(status=ReservationStatus.EXPIRED)
