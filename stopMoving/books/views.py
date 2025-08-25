# books/views.py
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.permissions import IsAuthenticated
from .serializers import StockBatchRequestSerializer
from .models import Book
from library.models import Library
from bookinfo.models import BookInfo, BookInfoLibrary
from bookinfo.serializers import DonationDisplaySerializer, PickupDisplaySerializer, BookDetailDisplaySerializer
from bookinfo.services import ensure_bookinfo
from django.db.models import Q, Count, F, Value, Sum
from math import radians, sin, cos, acos
from decimal import Decimal
from django.db import transaction
from users.models import UserInfo, Status
from accounts.models import User
from notification.service import push
from notification.models import Notification as N
from django.conf import settings
from django.db import transaction
from preferences.services.embeddings import deserialize_sparse, serialize_sparse, weighted_sum, l2_normalize
from users.models import UserBook
from .services import preference_books_activity, preference_books_combined, preference_notification
from typing import Tuple, Dict, Union

EARTH_KM = 6371.0
POINT_PER_BOOK = 500
DISCOUNT_RATE = Decimal("0.15")
# 《》
def message(first_title: str, count: int, verb: str) -> str:
    # verb: "기증 접수", "픽업 완료"
    return f"《{first_title}》 {verb}" if count == 1 else f"《{first_title}》 외 {count-1}권 {verb}"

def _increase_stock_one(library_id, isbn: str, qty: int):
    """
    해당 도서관 책 권 수 증가
    """
    isbn = BookInfo.objects.filter(isbn=isbn).first()
    if not isbn:
        return False, {"error": "책 정보가 없습니다. 먼저 BookInfo를 생성하세요.", "isbn": isbn}

    with transaction.atomic():
        bil, _created = (
            BookInfoLibrary.objects
            .select_for_update()
            .get_or_create(library_id=library_id, isbn=isbn, defaults={"quantity": 0})
        )
        BookInfoLibrary.objects.filter(pk=bil.pk).update(quantity=F("quantity") + qty)
        bil.refresh_from_db()

        if bil.quantity > 0 and bil.status != "AVAILABLE":
            bil.status = "AVAILABLE"
            bil.save(update_fields=["status"])

    return True, {
        "library_id": getattr(library_id, "id", None),
        "isbn": isbn.isbn,
        "added_quantity": qty,
        "total_quantity": bil.quantity,
        "status": bil.status,
    }

def _decrease_stock_one(library_id, isbn: str, qty: int) -> tuple[bool, dict, int]:
    """
    해당 도서관에서 특정 ISBN 재고(quantity) 감소.
    qty는 1 이상 정수.
    """

    bookinfo = BookInfo.objects.filter(isbn=isbn).first()
    if not bookinfo:
        return (False,
                {"isbn": isbn, "error": "책 정보가 없습니다. 먼저 BookInfo를 생성하세요."},
                status.HTTP_404_NOT_FOUND,
        )
    with transaction.atomic():
        bil = (
            BookInfoLibrary.objects
            .select_for_update()
            .filter(library_id=library_id, isbn=bookinfo)
            .first()
        )
        if not bil:
            return (False,
                    {"isbn": isbn, "error": "해당 도서관에 재고 항목이 없습니다."},
                    status.HTTP_404_NOT_FOUND,
            )
        
        if bil.status != "AVAILABLE":
            return (False,
                    {"isbn": isbn, "error": "구매 불가 상품입니다."},
                    status.HTTP_409_CONFLICT,
            )
        
        if bil.quantity < qty:
            return (False,
                    {"isbn": isbn, "error": "요청 권 수가 재고보다 많습니다."},
                    status.HTTP_409_CONFLICT,
            )        
        
        BookInfoLibrary.objects.filter(pk=bil.pk).update(quantity=F("quantity") - qty)
        bil.refresh_from_db()

        
        if bil.quantity == 0:
            bil.status = "PICKED" 
            bil.save(update_fields=["status"])

    return (True,{
        "library_id": getattr(library_id, "id", None),  
        "isbn": bookinfo.isbn,                           
        "removed_quantity": qty,                         
        "total_quantity": bil.quantity,
        "status": bil.status,
    }, status.HTTP_200_OK)

# 책 나눔하기 마지막에 나눔하기 버튼
class DonationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="도서 일괄 기증(단권/다권) — 입력은 library_id와 ISBN(문자열 or 문자열 리스트)",
        request_body=StockBatchRequestSerializer,
        responses={201: "생성됨", 400: "검증 오류", 404: "도서관 없음"}
    )
    def post(self, request):
        s = StockBatchRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        lib_id = v.get("library_id")

        try:
            lib_id = int(lib_id)
        except (TypeError, ValueError):
            return Response({"error": "library_id가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        
        library = Library.objects.filter(id=lib_id).first()
        if not library:
            return Response({"error": "해당 도서관이 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        results, success_cnt = [], 0
        success_isbn = [] # 기증 성공한 책 목록
        total_qty = 0
        point_cnt = 0

        for item in v["books"]:
            isbn_str = str(item["isbn"]).replace("-", "").strip()
            qty = int(item["quantity"])

            ok, out = _increase_stock_one(library, isbn_str, qty)
            if ok:
                success_cnt += 1
                results.append({"input": item, "status": "OK", "data": out})
                point_cnt += qty
                total_qty += qty
                success_isbn.append(isbn_str)
                UserBook.objects.create(
                    user=request.user,
                    bookinfo_id=isbn_str,  # to_field='isbn'
                    status="DONATED",
                    library_id=lib_id,
                    quantity=qty)

            else:
                results.append({"input": item, "status": "ERROR", "error": out})

            
        # 유저 포인트 증가 로직
        points_earned = point_cnt * POINT_PER_BOOK
        if request.user.is_authenticated and success_cnt > 0:
            user_info, _ = UserInfo.objects.get_or_create(user=request.user)
            user_info.points = (user_info.points or 0) + points_earned
            user_info.save(update_fields=["points"])
        
        # 알림 보내기
        if total_qty > 0:
            bi = BookInfo.objects.filter(isbn=success_isbn[0]).only("title").first()
            first_title = (bi.title if bi else None) or "도서"
            base_msg = message(first_title, total_qty,"을 나눔했어요!")
            msg = f"{base_msg}\n +{points_earned:,}P 적립"
            push(user=request.user,
                 type_="book_donated",
                 message=msg,
            )

        # 취향 일치하는 유저에게 알림 보내기
        preference_notification(donor_user=request.user, donated_isbns=success_isbn)

        return Response({
            "message": "일괄 기증 처리 완료",
            "library_id": library.id,
            "count_success": success_cnt,
            "count_total": len(v["books"]),
            "points_earned": points_earned,
        }, status=status.HTTP_201_CREATED)

# 책 가져가기 마지막에 가져가기 버튼
class PickupAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="도서 픽업(단권/다권) — 입력은 book_id(정수 또는 정수 리스트)",
        request_body=StockBatchRequestSerializer,
        responses={200: "처리됨", 400: "검증 오류"}
    )
    @transaction.atomic
    def post(self, request):
        s = StockBatchRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        lib_id = v.get("library_id")
        try:
            lib_id = int(lib_id)
        except (TypeError, ValueError):
            return Response({"error": "library_id가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        library = Library.objects.filter(id=lib_id).first()
        if not library:
            return Response({"error": "해당 도서관이 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        results, success_cnt = [], 0
        success_books = [] # 기증 성공한 책 목록
        any_success = False # 책 추천 기능 관련 플래그

        for item in v["books"]:
            isbn_str = str(item["isbn"]).replace("-", "").strip()
            qty = int(item["quantity"])
            ok, payload, code = _decrease_stock_one(library, isbn_str, qty)
            if ok:
                any_success = True
                # FIX: 성공 카운트 변수 오타
                success_cnt += 1
                # results.append({"input": item, "status": "OK", "data": out})
                success_books.append(isbn_str)

                results.append({
                    "isbn": item["isbn"],
                    "status": "PICKED",
                })
                with transaction.atomic():
                    UserBook.objects.create(
                        user=request.user,
                        bookinfo_id=isbn_str,  # to_field='isbn'
                        status="PURCHASED",
                        library_id=lib_id,
                        quantity=qty
                    )

                info = BookInfo.objects.filter(isbn=isbn_str).only("isbn", "title", "vector").first()
                if info:
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
                
            else:
                # 실패 케이스
                results.append({
                    "isbn": payload["isbn"],
                    "status": "FAILED",
                    "error": payload["error"],
                    "error_code": code})

        # 모든 save 끝난뒤 한 번만 등록        
        if any_success:
            def _after_commit(user_id):
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.using('default').get(id=user_id)  # 반드시 primary
                preference_books_combined(user, db_alias='default')
                preference_books_activity(user, db_alias='default')

            transaction.on_commit(lambda: _after_commit(request.user.id))
        
        # 알림 보내기
        if success_books:
            first_isbn = success_books[0]
            _bi = BookInfo.objects.filter(isbn=first_isbn).only("title").first()
            first_title = (_bi.title if _bi else None) or "도서"
            msg = message(first_title, len(success_books), "을 데려왔어요!\n 좋은 시간 보내세요")
            push(
                user=request.user,
                type_="book_pickup",     
                message=msg,
            )
        # 실제 시도한 건수
        attempted_cnt = len(v["books"])

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
            "pickup_error": http_status,
            "result": results
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
            BookInfoLibrary.objects
            .filter(isbn=isbn)
            .values('library_id__id', 'library_id__name', 'library_id__lat', 'library_id__long')
            .annotate(
                available_books=Sum('quantity', filter=Q(status='AVAILABLE')),
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
            la = row['library_id__lat']
            lo = row['library_id__long']  
            d_m = None
            if lat is not None and lng is not None and la is not None and lo is not None:
                φ1, φ2 = radians(lat), radians(float(la))
                Δλ = radians(float(lo) - lng)
                dist_km = acos(cos(φ1)*cos(φ2)*cos(Δλ) + sin(φ1)*sin(φ2)) * EARTH_KM
                d_m = int(round(dist_km * 1000))

            distance_display = None
            
            if d_m is not None:
                distance_display = f"{d_m/1000:.1f}km" if d_m >= 1000 else f"{d_m}m"
            
            libraries.append({
                "library_id": row["library_id__id"],
                "name": row["library_id__name"],
                "distance_m": distance_display,                 # 좌표 없으면 None
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
    스캔한 ISBN과 도서관 id로 픽업 상세 조회
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="스캔한 ISBN으로 책 정보와 해당 도서관의 AVAILABLE 책 id 목록 반환",
        manual_parameters=[
            openapi.Parameter(
                name="isbn",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                required=True,
                description="스캔한 ISBN(문자열)"
            ),
            openapi.Parameter(
                name="library_id",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                required=True,
                description="도서관 ID"
            ),
        ],
        responses={200: 'OK', 404: '책/도서관 없음', 400: '요청 오류'}
    )

    def get(self, request):
        isbn = request.GET.get("isbn")
        library_id = request.GET.get("library_id")

        # 1) 파라미터 검증
        if not isbn or not library_id:
            return Response({"error": "isbn과 library_id 모두 필요합니다."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            library_id = int(library_id)
        except ValueError:
            return Response({"error": "library_id는 정수입니다."},
                            status=status.HTTP_400_BAD_REQUEST)

        # 2) 도서관/책 존재 확인
        library = Library.objects.filter(id=library_id).only("id").first()
        if not library:
            return Response({"error": "해당 도서관이 존재하지 않습니다."},
                            status=status.HTTP_404_NOT_FOUND)

        info = BookInfo.objects.filter(isbn=isbn).first()
        if not info:
            return Response({"error": "해당 isbn의 책 정보가 없습니다."},
                            status=status.HTTP_404_NOT_FOUND)
        
        # 해당 도서관에 AVAILABLE인 책 정보 반환
        qs = (
            BookInfoLibrary.objects
            .filter(library_id=library_id, isbn=isbn, status="AVAILABLE")
        )

        available_cnt = int(qs.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0)


        # 도서관에 존재하는 책의 상태가 AVAILABLE가 아닐 때
        if available_cnt == 0:
            return Response({"error" : "구매 불가 상품입니다."},
                            status=status.HTTP_409_CONFLICT,)

        info_data = PickupDisplaySerializer(info).data
        data = {
            **info_data,
            "library_id": library_id,
            "status": "AVAILABLE" if available_cnt > 0 else "N/A",
            "is_pickable": available_cnt > 0,
            "available_count": available_cnt,
        }

        return Response({"data": data}, status=status.HTTP_200_OK)


        
