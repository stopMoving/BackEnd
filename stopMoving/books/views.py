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
from django.db.models import Q, Count, F, Value
from math import radians, sin, cos, acos
from decimal import Decimal

EARTH_KM = 6371.0
POINT_PER_BOOK = 500
DISCOUNT_RATE = Decimal("0.15")

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
        operation_description="도서 픽업(단권/다권) — 입력은 book_id(정수 또는 정수 리스트)",
        request_body=PickupSerializer,
        responses={200: "처리됨", 400: "검증 오류"}
    )
    def post(self, request):
        s = PickupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data

        library = Library.objects.filter(id=v["library_id"]).first()
        if not library:
            return Response({"error": "해당 도서관이 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        results, success_cnt = [], 0
        seen = set()  # 같은 id가 중복으로 올 때 중복 처리 방지

        for bid in v["book_id"]:
            if bid in seen:
                results.append({"book_id": bid, "status": "SKIPPED", "message": "중복 요청"})
                continue
            seen.add(bid)

            with transaction.atomic():
                # 재고 한 권을 잠그고 가져오기
                book = (Book.objects
                        .select_for_update()
                        .select_related("isbn", "library")
                        .filter(id=bid)
                        .first())

                if not book:
                    results.append({"book_id": bid, "status": "ERROR", "code": "NOT_FOUND", "message": "해당 책 없음"})
                    continue

                if book.status != "AVAILABLE":
                    results.append({
                        "book_id": bid, "status": "ERROR", "code": "NOT_AVAILABLE",
                        "message": f"현재 상태: {book.status}"
                    })
                    continue

                # 상태 전환
                book.status = "PICKED"
                book.save(update_fields=["status"])

                info = book.isbn  # BookInfo
                success_cnt += 1
                results.append({
                    "book_id": book.id,
                    "library_id": book.library_id,
                    "status": "PICKED",
                    # 정가 없으면 PickupDisplaySerializer가 sale_price=2000으로 내려줌
                    "book_info": PickupDisplaySerializer(info).data
                })

        return Response({
            "message": "픽업 처리 완료",
            "count_success": success_cnt,
            "count_total": len(v["book_id"]),
            "items": results
        }, status=status.HTTP_200_OK)
    
class BookDetailAPIView(APIView):
    def get(self, request, isbn):
        # 책 정보 가져오기
        try:
            info = BookInfo.objects.get(isbn=isbn)
        except BookInfo.DoesNotExist:
            return Response({"detail": "존재하지 않는 ISBN입니다."}, status=status.HTTP_404_NOT_FOUND)
        
        # 도서관 별 책 집계
        qs = (
            Book.objects
            .filter(isbn__isbn=isbn)
            .values('library_id', 'library__name', 'library__lat', 'library__long')
            .annotate(
                total_books=Count('id'),
                available_books=Count('id', filter=Q(status='AVAILABLE')),
            )
        )
        
        # 사용자 위치 받음
        lat = request.GET.get("lat")
        long = request.GET.get("long")
        try:
            lat = float(lat) if lat is not None else None
            long = float(long) if long is not None else None
        except ValueError:
            return Response({"detail": "lat/long 숫자여야 합니다."}, status=400)
        
        # 도서관~사용자 거리계산
        lat = request.GET.get("lat"); lng = request.GET.get("lng")
        try:
            lat = float(lat) if lat is not None else None
            lng = float(lng) if lng is not None else None
        except ValueError:
            return Response({"detail": "lat/lng는 숫자여야 합니다."}, status=400)

        
        libraries = []
        for row in qs:
            la = row['library__lat']
            lo = row['library__long']  # 🔁 모델 필드명이 long임
            d_m = None
            if lat is not None and lng is not None and la is not None and lo is not None:
                φ1, φ2 = radians(lat), radians(float(la))
                Δλ = radians(float(lo) - lng)
                dist_km = acos(cos(φ1)*cos(φ2)*cos(Δλ) + sin(φ1)*sin(φ2)) * EARTH_KM
                d_m = int(round(dist_km * 1000))

            libraries.append({
                "library_id": row["library_id"],
                "name": row["library__name"],
                "distance_m": d_m,                 # 좌표 없으면 None
                "total_books": row["total_books"],
                "available_books": row["available_books"],
            })

        # 5) 거리 기준 정렬 (있으면 앞으로)
        if lat is not None and lng is not None:
            libraries.sort(key=lambda x: (x["distance_m"] is None, x["distance_m"] or 0))

        # 6) 책 메타 + 도서관 목록
        info_data = PickupDisplaySerializer(info).data
        return Response({**info_data, "summary": getattr(info, "summary", None), "libraries": libraries}, status=200)

        
