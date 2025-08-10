from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema

from .serializers import DonationSerializer, PickupSerializer
from .models import Book
from library.models import Library
from bookinfo.models import BookInfo
from bookinfo.serializers import DonationDisplaySerializer, PickupDisplaySerializer

POINT_PER_BOOK = 500

class DonationAPIView(APIView):
    """
    여러 권(또는 1권) 기증 확정:
    - 각 항목마다 BookInfo get_or_create
    - Book 재고 1권씩 생성
    - 성공 건수 * 500p 반환
    """
    @swagger_auto_schema(
        operation_description="도서 일괄 기증(단권/다권 모두 지원)",
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

        results = []
        success_cnt = 0

        for item in v["items"]:
            try:
                info, created = BookInfo.objects.get_or_create(
                    isbn=item["isbn"],
                    defaults={
                        "title": item.get("title", "") or "",
                        "author": item.get("author", "") or "",
                        "publisher": item.get("publisher", "") or "",
                        "regular_price": item.get("regular_price"),
                    },
                )
                # 정가 보강
                if (not created) and info.regular_price is None and item.get("regular_price") is not None:
                    info.regular_price = item["regular_price"]
                    info.save(update_fields=["regular_price"])

                book = Book.objects.create(
                    library=library,
                    isbn=info,
                    regular_price=item.get("regular_price") or info.regular_price,
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
                results.append({
                    "isbn": item["isbn"],
                    "status": "ERROR",
                    "message": str(e),
                })

        return Response({
            "message": "일괄 기증 처리 완료",
            "library_id": library.id,
            "count_success": success_cnt,
            "count_total": len(v["items"]),
            "points_earned": success_cnt * POINT_PER_BOOK,  # 권당 500p
            "items": results
        }, status=status.HTTP_201_CREATED)

class PickupAPIView(APIView):
    """
    여러 권(또는 1권) 픽업:
    - 각 항목마다 해당 도서관에서 AVAILABLE 1권을 잠그고 PICKED로 변경
    - DB에 정가 없고 요청값 있으면 보강
    - 부분 성공 허용(항목별 성공/실패 결과 반환)
    """
    @swagger_auto_schema(
        operation_description="도서 일괄 픽업(단권/다권 모두 지원)",
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

        results = []
        success_cnt = 0

        for item in v["items"]:
            with transaction.atomic():
                info = BookInfo.objects.filter(isbn=item["isbn"]).first()
                if not info:
                    results.append({"isbn": item["isbn"], "status": "ERROR", "message": "ISBN 메타 없음"})
                    continue

                # 재고 1권 잠그고 가져오기 (가장 오래된 것 우선)
                book = (Book.objects
                        .select_for_update()
                        .filter(library=library, isbn=info, status="AVAILABLE")
                        .order_by("donation_date")
                        .first())
                if not book:
                    results.append({"isbn": item["isbn"], "status": "ERROR", "message": "재고 없음"})
                    continue

                # 정가 보강(DB 없고 요청값 있으면)
                if info.regular_price is None and item.get("regular_price") is not None:
                    info.regular_price = item["regular_price"]
                    info.save(update_fields=["regular_price"])

                # 상태 전환
                book.status = "PICKED"
                book.save(update_fields=["status"])

                success_cnt += 1
                results.append({
                    "isbn": info.isbn,
                    "book_id": book.id,
                    "status": "PICKED",
                    "book_info": PickupDisplaySerializer(info).data  # 정가 + 85% 판매가 포함
                })

        return Response({
            "message": "일괄 픽업 처리 완료",
            "library_id": library.id,
            "count_success": success_cnt,
            "count_total": len(v["items"]),
            "items": results
        }, status=status.HTTP_200_OK)
