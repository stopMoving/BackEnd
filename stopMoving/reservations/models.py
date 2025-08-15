from django.db import models
from library.models import Library
from bookinfo.models import BookInfo
from users.models import User
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.core.exceptions import ValidationError
from celery import shared_task
from django.db.models import F, Q
# Create your models here.
# models.py

# 도서관별 책 권수
class LibraryBookStock(models.Model):
    library = models.ForeignKey(Library, on_delete=models.CASCADE)
    book_info = models.ForeignKey(BookInfo, on_delete=models.CASCADE)
    total_count = models.IntegerField()  # 총 보유 수량
    available_count = models.IntegerField()  # 현재 가능 수량

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('library', 'book_info'), name='uniq_library_book'),
            models.CheckConstraint(check=Q(total_count__gte=0), name='chk_total_nonneg'), # 총권수가 0 이상  
            models.CheckConstraint(check=Q(available_count__gte=0), name='chk_available_nonneg'), # 가능한 권수가 0 이상
            models.CheckConstraint(check=Q(available_count__lte=F('total_count')), name='chk_available_le_total'), # availalbe한 책이 total보다 작거나 같음
        ]
        indexes = [models.Index(fields=['library', 'book_info'])]
    
    def __str__(self):
        return f"{self.library.name} - {self.book_info.title} ({self.available_count}/{self.total_count})"

# 상태
class ReservationStatus(models.TextChoices):
    ACTIVE = 'active', '예약중'
    EXPIRED = 'expired', '만료'
    PICKED_UP = 'picked_up', '대출완료'
    CANCELLED = 'cancelled', '취소'

# 예약 테이블
class BookReservation(models.Model):
    # pk 자동 생성
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book_stock = models.ForeignKey(LibraryBookStock, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)  # 한 건에 여러 권 예약가능
    reserved_at = models.DateTimeField(auto_now_add=True) # 예약시간
    expires_at = models.DateTimeField() # 예약시간 + 3시간
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.ACTIVE,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True) 

    class Meta:
        indexes = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['user', 'status']),
        ]
        constraints = [
            models.CheckConstraint(check=Q(quantity__gte=1), name='chk_quantity_ge_1'), # 예약 가능 권수가 1권 이상인지 확인
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=3)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.book_stock.book_info.title} x{self.quantity} ({self.status})"

# 예약 요청 시 예약 테이블 생성
# 키워드 파라미터 사용 예약시 기본 수량은 1로 고정
def create_reservation(*, user=User, library=Library, book_info=BookInfo, quantity: int = 1) -> BookReservation:
    if quantity < 1:
        raise ValidationError("수량은 1이상이어야 합니다.")
    
    with transaction.atomic():
        try:
            stock = (LibraryBookStock.objects
                     .select_for_update()
                     .get(library=library, book_info=book_info))
        except LibraryBookStock.DoesNotExist:
            raise ValidationError("해당 도서관에 책이 존재하지 않습니다.")
        
        update = (LibraryBookStock.objects
                  .filter(pk=stock.pk, available_count__gte=quantity) # 가능권수가 예약 요청 권 수 보다 큰 것만 가져옴
                  .update(available_count=F('available_count')-quantity)) # 가능권수에서 요청권수를 빼서 업데이트
        # 가능 권수가 요청 권 수보다 작으면 
        if update == 0:
            raise ValidationError("요청 수량만큼 예약 가능한 책이 없습니다.")
        
        reservation = BookReservation.objects.create(
            user=user,
            book_stock=stock,
            quantity=quantity,
        )

        return reservation

def cancel_reservation(*, user=User, reservation_id: int) -> BookReservation:
    """예약 전체 취소 - 수량만큼 재고 복구"""
    with transaction.atomic():
        try:
            reservation = (BookReservation.objects
                           .select_for_update()
                           .get(id=reservation_id, user=user, status=ReservationStatus.ACTIVE))
        except BookReservation.DoesNotExist:
            raise ValidationError("예약이 존재하지 않습니다.")
        
        # 수량 다시 채우기
        LibraryBookStock.objects.filter(pk=reservation.book_stock_id).update(available_count=F('available_count') + reservation.quantity)

        reservation.status = ReservationStatus.CANCELLED
        reservation.save(update_fields=['status', 'updated_at'])
        return reservation

def pick_up_reservation(*, user=User, reservation_id:int) -> bool:
    """픽업 완료 -> 재고 복구 없이 상태 변경만"""
    with transaction.atomic():
        try:
            reservation = (BookReservation.objects
                        .select_for_update()
                        .get(id=reservation_id, user=user, status=ReservationStatus.ACTIVE))
        except BookReservation.DoesNotExist:
            raise ValidationError("예약이 존재하지 않습니다.")
        
        # 예약 상태가 아니면 false
        if reservation.status != ReservationStatus.ACTIVE:
            return False
        
        # 상태만 변경하기
        reservation.status = ReservationStatus.PICKED_UP
        reservation.save(update_fields=['status', 'updated_at'])
        return True