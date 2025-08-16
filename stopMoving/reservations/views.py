# appname/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from users.models import UserBook, Status
from .models import BookReservation
from books.models import Book
from django.db import transaction
from .serializers import (
    CreateReservationSerializer,
    ReservationCancelSerializer,
    ReservationPickUpSerializer,
    ReservationListItemSerializer,
)


class BookReservationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """도서 예약하기 (quantity 지원)"""
        s = CreateReservationSerializer(data=request.data, context={'request': request})
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            reservation = s.save()
            reservation.book_stock.refresh_from_db(fields=['available_count'])
            data = {
                "message": "예약이 완료되었습니다.",
                "reservation_id": reservation.id,
                "quantity": reservation.quantity,
                "expires_at": reservation.expires_at,
                "book_title": reservation.book_stock.isbn.title,
                "library_name": reservation.book_stock.library.name,
            }
            return Response(data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ReservationCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reservation_id):
        """예약 전체 취소"""
        s = ReservationCancelSerializer(data={"reservation_id": reservation_id}, context={'request': request})
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            reservation = s.save()
            reservation.book_stock.refresh_from_db(fields=['available_count'])
            return Response({
                "message": "예약이 취소되었습니다.",
                "reservation_id": reservation.id,
                "quantity_refunded": reservation.quantity
            })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ReservationPickupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reservation_id):
        """픽업 완료 처리"""
        s = ReservationPickUpSerializer(data={"reservation_id": reservation_id}, context={'request': request})
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            resv = get_object_or_404(
                BookReservation.objects.select_related('book_stock__library', 'book_stock__isbn'),
                id=reservation_id, user=request.user
            )


            
        
        try:
            s.save()

            UserBook.objects.get_or_create(
                    user=request.user,
                    # book=book,
                    defaults={"status": Status.PURCHASED},
                )
            
            return Response({"message": "픽업 완료되었습니다.", "reservation_id": reservation_id})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserReservationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """내 예약 목록"""
        qs = (BookReservation.objects
              .filter(user=request.user)
              .select_related('book_stock__isbn', 'book_stock__library')
              .order_by('-reserved_at'))
        data = ReservationListItemSerializer(qs, many=True).data
        return Response(data)
