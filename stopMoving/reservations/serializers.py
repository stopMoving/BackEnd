from rest_framework import serializers
from django.core.exceptions import ValidationError
from library.models import Library
from bookinfo.models import BookInfo
from .models import BookReservation, cancel_reservation, create_reservation, pick_up_reservation

# 예약 생성
class CreateReservationSerializer(serializers.Serializer):
    library_id = serializers.IntegerField()
    isbn = serializers.CharField()
    quantity = serializers.IntegerField(required=False, default=1, min_value=1)

    def create(self, data):
        user = self.context['request'].user
        library = Library.objects.get(pk=data['library_id'])
        isbn = BookInfo.objects.get(pk=data['isbn'])

        return create_reservation(
            user=user,
            library=library,
            isbn=isbn,
            quantity=data['quantity']
        )

class ReservationCancelSerializer(serializers.Serializer):
    reservation_id = serializers.IntegerField()

    def create(self, data):
        user = self.context['request'].user
        return cancel_reservation(user=user, reservation_id=data['reservation_id'])

class ReservationPickUpSerializer(serializers.Serializer):
    reservation_id = serializers.IntegerField()

    def create(self, data):
        user = self.context['request'].user
        pick_up = pick_up_reservation(user=user, reservation_id=data['reservation_id'])
        if not pick_up:
            raise ValidationError("이미 만료/취소/픽업된 예약입니다.")
        return pick_up

# 예약 목록
class ReservationListItemSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book_stock.isbn.title')
    library_name = serializers.CharField(source='book_stock.library.name')
    

    class Meta:
        model = BookReservation
        fields = ['id', 'user_id', 'book_title', 'library_name', 'quantity', 'reserved_at', 'expires_at', 'status']
        