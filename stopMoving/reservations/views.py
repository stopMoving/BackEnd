# appname/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import BookReservation
from .serializers import (
    CreateReservationSerializer,
    ReservationCancelSerializer,
    ReservationPickupSerializer,
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
            data = {
                "message": "예약이 완료되었습니다.",
                "reservation_id": reservation.id,
                "quantity": reservation.quantity,
                "expires_at": reservation.expires_at,
                "book_title": reservation.book_stock.book_info.title,
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
            resv = s.save()
            return Response({
                "message": "예약이 취소되었습니다.",
                "reservation_id": resv.id,
                "quantity_refunded": resv.quantity
            })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ReservationPickupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reservation_id):
        """픽업 완료 처리"""
        s = ReservationPickupSerializer(data={"reservation_id": reservation_id}, context={'request': request})
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            s.save()
            return Response({"message": "픽업 완료되었습니다.", "reservation_id": reservation_id})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserReservationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """내 예약 목록"""
        qs = (BookReservation.objects
              .filter(user=request.user)
              .select_related('book_stock__book_info', 'book_stock__library')
              .order_by('-reserved_at'))
        data = ReservationListItemSerializer(qs, many=True).data
        return Response(data)
