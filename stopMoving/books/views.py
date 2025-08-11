# books/views.py
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import IsAuthenticated
from .serializers import DonationSerializer, PickupSerializer
from .models import Book
from library.models import Library
from bookinfo.models import BookInfo
from bookinfo.serializers import DonationDisplaySerializer, PickupDisplaySerializer
from bookinfo.services import ensure_bookinfo

POINT_PER_BOOK = 500

class DonationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="도서 일괄 기증(단권/다권) — 입력은 library_id와 ISBN(문자열 or 문자열 리스트)",
        request_body=DonationSerializer,
        responses={201: "생성됨", 400: "검증 오류", 404: "도서관 없음"}
    )
    def post(self, request):
        s = DonationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data

        library = Library.objects.filter(id=v["library_id"]).first()
        if not library:
            return Response({"error": "해당 도서관이 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        results, success_cnt = [], 0
        cache = {}

        for isbn in v["isbn"]:
            try:
                info = cache.get(isbn) or ensure_bookinfo(isbn)
                if not info:
                    results.append({
                        "isbn": isbn,
                        "status": "ERROR",
                        "code": "BOOKINFO_REQUIRED",
                        "message": "책 정보가 없습니다."
                    })
                    continue
                cache[isbn] = info

                book = Book.objects.create(
                    library=library,
                    isbn=info,
                    regular_price=info.regular_price,  # 정가 정보 없으면 None 저장
                    donor_user=request.user if request.user.is_authenticated else None,
                )
                success_cnt += 1
                results.append({
                    "isbn": info.isbn,
                    "book_id": book.id,
                    "status": "CREATED",
                    "book_info": DonationDisplaySerializer(info).data
                })
            except Exception as e:
                results.append({"isbn": isbn, "status": "ERROR", "message": str(e)})

        return Response({
            "message": "일괄 기증 처리 완료",
            "library_id": library.id,
            "count_success": success_cnt,
            "count_total": len(v["isbn"]),
            "points_earned": success_cnt * POINT_PER_BOOK,
            "items": results
        }, status=status.HTTP_201_CREATED)


class PickupAPIView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="도서 일괄 픽업(단권/다권) — 입력은 library_id와 ISBN 리스트만",
        request_body=PickupSerializer,
        responses={200: "처리됨", 400: "검증 오류", 404: "도서관 없음"}
    )
    def post(self, request):
        s = PickupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data

        library = Library.objects.filter(id=v["library_id"]).first()
        if not library:
            return Response({"error": "해당 도서관이 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        results, success_cnt = [], 0
        cache = {}

        for isbn in v["isbn"]:
            with transaction.atomic():
                info = cache.get(isbn) or ensure_bookinfo(isbn)
                if not info:
                    results.append({
                        "isbn": isbn, "status": "ERROR",
                        "code": "BOOKINFO_REQUIRED",
                        "message": "도서 메타가 없습니다. 먼저 /bookinfo/lookup을 호출하세요."
                    })
                    continue
                cache[isbn] = info

                # 재고 잠그고 1권 가져오기
                book = (Book.objects
                        .select_for_update()
                        .filter(library=library, isbn=info, status="AVAILABLE")
                        .order_by("donation_date")
                        .first())
                if not book:
                    results.append({"isbn": isbn, "status": "ERROR", "message": "재고 없음"})
                    continue

                book.status = "PICKED"
                book.save(update_fields=["status"])

                success_cnt += 1
                results.append({
                    "isbn": info.isbn,
                    "book_id": book.id,
                    "status": "PICKED",
                    "book_info": PickupDisplaySerializer(info).data  # regular_price + sale_price(85%할인), #정가 정보 없으면 고정 2000원
                })

        return Response({
            "message": "일괄 픽업 처리 완료",
            "library_id": library.id,
            "count_success": success_cnt,
            "count_total": len(v["isbn"]),
            "items": results
        }, status=status.HTTP_200_OK)
