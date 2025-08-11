# bookinfo/views.py
import re, requests
from django.db import IntegrityError
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.permissions import IsAuthenticated

from .models import BookInfo
from bookinfo.serializers import (
    DonationDisplaySerializer,
    PickupDisplaySerializer,
    BookInfoUpsertSerializer,
)

class BookLookUpAPIView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="ISBN으로 도서 정보 조회 (DB 없으면 알라딘 저장 후 반환)",
        manual_parameters=[
            openapi.Parameter('isbn', openapi.IN_QUERY, description="ISBN(10/13자리, 하이픈 허용)", type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('purpose', openapi.IN_QUERY, description="용도(donation | pickup)", type=openapi.TYPE_STRING, required=False),
        ],
        responses={200: 'DB 조회 성공', 201: '알라딘 조회 후 생성', 400: '잘못된 요청', 404: '결과 없음', 502: '외부 API 오류'}
    )
    def get(self, request):
        raw = request.query_params.get('isbn')
        purpose = (request.query_params.get('purpose') or 'donation').lower()
        if not raw:
            return Response({"error": "ISBN이 필요합니다."}, status=400)

        isbn = raw.replace("-", "").strip()
        if not re.fullmatch(r"\d{10}|\d{13}", isbn):
            return Response({"error": "ISBN 형식이 올바르지 않습니다(10 또는 13자리)."}, status=400)

        # 1) DB 먼저
        book = BookInfo.objects.filter(isbn=isbn).first()
        if book:
            data = self._serialize_for_purpose(book, purpose)
            data["meta"] = {"source": "db"}
            return Response(data, status=200)

        # 2) 알라딘 조회
        url = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
        params = {
            "ttbkey": settings.API_KEY,
            "itemIdType": "ISBN13" if len(isbn) == 13 else "ISBN",
            "ItemId": isbn,
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

        out = self._serialize_for_purpose(obj, purpose)
        out["meta"] = {"source": "aladin"}
        return Response(out, status=201)

    def _serialize_for_purpose(self, obj, purpose: str) -> dict:
        if purpose == "pickup":
            return PickupDisplaySerializer(obj).data
        # 기본: donation
        return DonationDisplaySerializer(obj).data
