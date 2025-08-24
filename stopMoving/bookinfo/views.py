# bookinfo/views.py
import re, requests
from django.db import IntegrityError
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Func, F, Value,Window
from users.models import UserInfo
from .models import BookInfo
import random
from django.db.models.expressions import RawSQL
from django.db.models.functions import RowNumber
from bookinfo.serializers import (
    PickupDisplaySerializer,
    BookInfoUpsertSerializer,
    BookSummarySerializer,
)

# 책 기증할 때 책 정보 불러오는 API
class DonateBookLookUpAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="ISBN으로 도서 메타 조회 (DB 없으면 알라딘 저장 후 반환)",
        manual_parameters=[openapi.Parameter('isbn', openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True)],
        responses={200: 'DB 조회', 201: '알라딘 조회 후 생성', 400: '형식 오류', 404: '없음', 502: '외부 오류'}
    )

    def get(self, request):
        raw = request.query_params.get('isbn')
        
        if not raw:
            return Response({"error": "ISBN이 필요합니다."}, status=400)

        isbn = raw.replace("-", "").strip()
        # if not re.fullmatch(r"\d{10}|\d{13}", isbn):
        #     return Response({"error": "ISBN 형식이 올바르지 않습니다(10 또는 13자리)."}, status=400)

        # 1) DB 먼저
        obj = BookInfo.objects.filter(isbn=isbn).first()
        if obj:
            #기증이지만 saleprice필요해서 픽업시리얼라이저
            data = PickupDisplaySerializer(obj).data
            data["meta"] = {"source": "db"}
            return Response(data, status=200)

        # 2) 알라딘 조회
        url = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
        params = {
            "ttbkey": settings.API_KEY,
            "itemIdType": "ISBN13" if len(isbn) == 13 else "ISBN",
            "ItemId": isbn,
            "Cover": "Big",
            "output": "js",
            "Version": "20131101",
            "OptResult": "packing",
        }
        try:
            r = requests.get(url, params=params, timeout=5)
            r.raise_for_status()
            payload = r.json()
            items = payload.get("item") or []
            if not items:
                return Response({"error": "해당 ISBN의 도서 정보를 찾을 수 없습니다."}, status=404)
            item = items[0]
        except requests.Timeout:
            return Response({"error": "알라딘 API 요청 시간 초과"}, status=502)
        except (requests.RequestException, ValueError) as e:
            return Response({"error": f"알라딘 API 오류: {e}"}, status=502)

        upsert = BookInfoUpsertSerializer(data={
            "isbn": isbn,
            "title": item.get("title", "") or "",
            "author": item.get("author", "") or "",
            "publisher": item.get("publisher", "") or "",
            "published_date": item.get("pubDate"),
            "cover_url": item.get("cover", "") or "",
            "category": item.get("categoryName", "") or "",
            "regular_price": item.get("priceStandard") or None,
            "description": item.get("description", "") or "",
        })
        upsert.is_valid(raise_exception=True)
        try:
            obj = upsert.save()
        except IntegrityError:
            obj = BookInfo.objects.get(isbn=isbn)

        # 기증이지만 saleprice필요해서 pickup시리얼라이저 사용
        data = PickupDisplaySerializer(obj).data
        data["meta"] = {"source": "aladin"}
        return Response(data, status=201)

    
# 책 검색
class BookSearchAPIView(APIView):
    
    @swagger_auto_schema(manual_parameters=[
        openapi.Parameter('q', openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True, description="검색어"),
        openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False),
        openapi.Parameter('page_size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False),
    ])
    def get(self, request):
        q = request.GET.get('q', '').strip()
        if not q:
            return Response({"detail": "q는 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        
        keywords = q.split()

        # 공백 무시용 임시필드
        base = BookInfo.objects.annotate(
            title_no_space=Func(F('title'), Value(' '), Value(''), function='REPLACE')
        )

        # 단어 모두 포함(AND) + 공백무시 매칭
        cond = Q()
        for w in keywords:
            nw = w.replace(' ', '')
            cond &= (
                Q(title__icontains=w) |
                Q(author__icontains=w) |
                Q(isbn__icontains=w) |
                Q(title_no_space__icontains=nw)
            )

        qs = base.filter(cond).order_by('title')

        # 페이지네이션
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        start, end = (page - 1) * page_size, page * page_size
        
        # 검색어에 맞는 책이 없을 경우
        if len(qs) == 0:
            search_q = request.GET.get('q', '')
            msg = f'"{search_q}" 은\n북작북작에 나눔되지 않았습니다.'

            isbn_list = []
            ui = UserInfo.objects.filter(user=request.user).only('preference_book_combined').first()
            isbn_list = ui.preference_book_combined
            rand_index = random.randint(0,4)
            recommend_isbn = isbn_list[rand_index]

            obj = BookInfo.objects.get(isbn=recommend_isbn)

            data = BookSummarySerializer(obj).data

            return Response({"msg":msg, "data": data})
        


        # 프론트에 필요한 필드만 반환 (제목/저자/출판사/출간일/표지)
        results = [{
            "isbn": b.isbn,
            "title": b.title,
            "author": b.author,
            "publisher": getattr(b, "publisher", None),
            "published_date": getattr(b, "published_date", None),
            "cover_url": getattr(b, "cover_url", None)
        } for b in qs[start:end]]

        return Response({"count": qs.count(), "results": results}, status=200)
        
# 설문조사 시 책 목록 보여주기용
class BookListView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_summary="전체 책 목록(간략) 조회",
        operation_description="설문용 카드 목록. isbn, title, author, publisher, cover_url만 반환합니다.",
        responses={200: BookSummarySerializer(many=True)}
    )
    def get(self, request):
        qs = (
            BookInfo.objects
            .annotate(
                second_cat=RawSQL(
                    "SUBSTRING_INDEX(SUBSTRING_INDEX(category, '>', 2), '>', -1)", []
                ),
                rn=Window(
                    expression=RowNumber(),
                    partition_by=[F("second_cat")],
                    order_by=F("published_date").desc(),
                ),
            )
            .filter(rn=1)
            .values("second_cat", "cover_url", "isbn")     # <- 충돌 회피
            .order_by("second_cat")
        )

        result = [{"category": row["second_cat"], "cover_url": row["cover_url"], "isbn": row["isbn"]} for row in qs]
        return Response(result, status=status.HTTP_200_OK)