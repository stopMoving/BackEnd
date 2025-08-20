# books/views.py
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.permissions import IsAuthenticated
from .serializers import DonationSerializer, PickupSerializer
from .models import Book
from library.models import Library
from bookinfo.models import BookInfo
from bookinfo.serializers import DonationDisplaySerializer, PickupDisplaySerializer, BookDetailDisplaySerializer
from bookinfo.services import ensure_bookinfo
from django.db.models import Q, Count, F, Value
from math import radians, sin, cos, acos
from decimal import Decimal
from django.db import transaction
from users.models import UserInfo, UserBook, Status
from notification.service import push
from notification.models import Notification as N
from django.conf import settings
from django.db import transaction
from preferences.services.embeddings import deserialize_sparse, serialize_sparse, weighted_sum, l2_normalize

EARTH_KM = 6371.0
POINT_PER_BOOK = 500
DISCOUNT_RATE = Decimal("0.15")

def message(first_title: str, count: int, verb: str) -> str:
    # verb: "기증 접수", "픽업 완료"
    return f"<<{first_title}>> {verb}" if count == 1 else f"<<{first_title}>> 외 {count-1}권 {verb}"

# 책 나눔하기 마지막에 나눔하기 버튼
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
        success_books = [] # 기증 성공한 책 목록

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
                    sale_price=info.sale_price,
                    donor_user=request.user if request.user.is_authenticated else None,
                )

                UserBook.objects.get_or_create(
                    user=request.user,
                    book=book,
                    defaults={"status": Status.DONATED},
                )

                success_cnt += 1
                success_books.append(book)
                results.append({
                    "isbn": info.isbn,
                    "book_id": book.id,
                    "status": "CREATED",
                    "book_info": DonationDisplaySerializer(info).data
                })
            except Exception as e:
                results.append({"isbn": isbn, "status": "ERROR", "message": str(e)})
            
        # 유저 포인트 증가 로직
        points_earned = success_cnt * POINT_PER_BOOK
        if request.user.is_authenticated and success_cnt > 0:
            user_info, _ = UserInfo.objects.get_or_create(user=request.user)
            user_info.points = (user_info.points or 0) + points_earned
            user_info.save(update_fields=["points"])
        
        # 알림 보내기
        if success_books:
            first = getattr(success_books[0].isbn, "title", "도서")
            base_msg = message(first, len(success_books),"을 나눔했어요!")
            msg = f"{base_msg}\n+{points_earned:,} P 적립"
            push(user=request.user,
                 type_="book_donated",
                 message=msg,
            )

        return Response({
            "message": "일괄 기증 처리 완료",
            "library_id": library.id,
            "count_success": success_cnt,
            "count_total": len(v["isbn"]),
            "points_earned": points_earned,
            "items": results
        }, status=status.HTTP_201_CREATED)

# 책 가져가기 마지막에 가져가기 버튼
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

        results, success_cnt = [], 0
        seen = set()  # 같은 id가 중복으로 올 때 중복 처리 방지
        success_books = [] # 픽업 성공한 책 목록

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

                UserBook.objects.get_or_create(
                    user=request.user,
                    book=book,
                    defaults={"status": Status.PURCHASED},
                )
                info = book.isbn  # BookInfo
                # 취향 벡터 계산 위해 추가---------------------
                ui, _ = UserInfo.objects.get_or_create(user = request.user)

                book_v = deserialize_sparse(info.vector)
                if book_v is not None:
                    # 활동 벡터 EMA 업데이트
                    beta = settings.ACTIVITY_EMA_BETA
                    old_act = deserialize_sparse(ui.preference_vector_activity)
                    new_act = book_v if old_act is None else (beta * old_act + (1 - beta) * book_v)
                    ui.preference_vector_activity = serialize_sparse(new_act)

                    # 통합 벡터 갱신: α*survey + (1-α)*activity
                    survey = deserialize_sparse(ui.preference_vector_survey)
                    combined = weighted_sum(survey, new_act, alpha = settings.RECOMMEND_ALPHA)
                    # l2 정규화 추가
                    combined = l2_normalize(combined)
                    ui.preference_vector = serialize_sparse(combined if combined is not None else new_act)

                    ui.save(update_fields=["preference_vector_activity", "preference_vector"])

                # 기존 코드-------------------------
                success_cnt += 1
                success_books.append(book)
                results.append({
                    "book_id": book.id,
                    "library_id": book.library_id,
                    "status": "PICKED",
                    # 정가 없으면 PickupDisplaySerializer가 sale_price=2000으로 내려줌
                    "book_info": PickupDisplaySerializer(info).data
                })
        
        # 알림 보내기
        if success_books:
            first_title = getattr(success_books[0].isbn, "title", None) or "도서"
            msg = message(first_title, len(success_books), "을 데려왔어요!\n좋은 시간 보내세요")
            push(
                user=request.user,
                type_="book_pickup",     
                message=msg,
            )
        # 실제 시도한(중복 제거된) 건수로 계산
        attempted_cnt = len(seen)

        
        if success_cnt == 0:
            msg = "픽업 실패"
            http_status = status.HTTP_409_CONFLICT
        elif success_cnt < attempted_cnt:
            msg = "일부 픽업 처리"
            http_status = status.HTTP_207_MULTI_STATUS
        else:
            msg = "픽업 처리 완료"
            http_status = status.HTTP_200_OK

        return Response({
            "message": msg,                         
            "count_success": success_cnt,
            "count_total": attempted_cnt,           
            "items": results
        }, status=http_status)      

# 책 검색 목록에서 책을 선택했을 때
class BookDetailAPIView(APIView):
    @swagger_auto_schema(
        operation_description="ISBN으로 책 메타 + 도서관별 재고 및 거리 조회",
        manual_parameters=[
            openapi.Parameter('isbn', openapi.IN_PATH, type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('lat', openapi.IN_QUERY, type=openapi.TYPE_NUMBER, required=False, description="사용자 위도"),
            openapi.Parameter('lng', openapi.IN_QUERY, type=openapi.TYPE_NUMBER, required=False, description="사용자 경도"),
        ],
        responses={200: 'OK', 404: '존재하지 않는 ISBN', 400: '요청 오류'}
    )

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
            .filter(available_books__gt=0)
        )
        
        # 사용자 위치 받음
        lat_str = request.GET.get("lat")
        lng_str = request.GET.get("lng")
        try:
            lat = float(lat_str) if lat_str is not None else None
            lng = float(lng_str) if lng_str is not None else None
        except ValueError:
            return Response({"detail": "lat/lng 숫자여야 합니다."}, status=400)
        
        # 거리 계산
        libraries = []
        for row in qs:
            la = row['library__lat']
            lo = row['library__long']  
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
        info_data = BookDetailDisplaySerializer(info).data
        return Response({**info_data, "libraries": libraries}, status=200)

class PickUpBookDetailAPIView(APIView):
    """
    스캔으로 받은 book_id(개별 권)로 상세 조회 (DB only)
    GET /api/books/{book_id}/
    """
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="스캔한 book_id로 픽업용 상세 조회",
        manual_parameters=[
            openapi.Parameter('book_id', openapi.IN_PATH, type=openapi.TYPE_INTEGER, required=True),
        ],
        responses={200: 'OK', 404: '없음', 400: '요청 오류'}
    )

    def get(self, request, book_id: int):
        try:
            b = Book.objects.select_related('isbn').get(id=book_id)
        except Book.DoesNotExist:
            return Response({"error": "해당 book_id가 없습니다."}, status=404)
        
        info_data = PickupDisplaySerializer(b.isbn).data

        data = {
            **info_data,
            "status": b.status,
            "is_pickable": (b.status == "AVAILABLE")
        }
        return Response(data, status=200)
        
