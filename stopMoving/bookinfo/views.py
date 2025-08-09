from django.shortcuts import render
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import BookInfo
from .serializers import BookInfoSerializer
# Create your views here.

class BookLookUpAPIView(APIView):
    @swagger_auto_schema(
        operation_description="ISBN으로 도서 정보 조회",
        manual_parameters=[
            openapi.Parameter(
                'isbn', openapi.IN_QUERY, description="ISBN 코드", type=openapi.TYPE_STRING, required=True
            )
        ],
        responses={200: '성공', 400: '잘못된 요청', 502: '외부 API 오류'}
    )
    def get(self, request):
        isbn = request.query_params.get('isbn') # 프론트에서 넘겨주는 isbn
        if not isbn:
            return Response({"error": "ISBN이 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Db에서 먼저 책 조회
        book = BookInfo.objects.filter(isbn=isbn).first()
        if book:
            # Model instance → dict 변환
            return Response({
                "isbn": book.isbn,
                "title": book.title,
                "author": book.author,
                "publisher": book.publisher,
                "published_date": book.published_date,
                "cover_url": book.cover_url,
                "category": book.category,
                "regular_price": book.regular_price,
                "description": book.description
            }, status=status.HTTP_200_OK)
        
        # 알라딘 API 호출
        url = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
        params = {
            "ttbkey": settings.API_KEY,
            "itemIdType": "ISBN13",
            "ItemId": isbn,
            "output": "js",
            "Version": "20131101",
            "OptResult": "packing"
        }

        try:
            res = requests.get(url, params=params, timeout=5)
            res.raise_for_status()
            data = res.json() #응답을 data에 저장
        except requests.RequestException as e:
            return Response({"error": f"API 요청 실패: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError:
            return Response({"error": "ISBN 결과 없음"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # 필요한 데이터만 추출
        try:
            item = data["item"][0]
        except (KeyError, IndexError):
            return Response({"error": "API에서 책 데이터를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        # DB 저장 (Serializer로 검증 + 저장)
        serializer = BookInfoSerializer(data={
            "isbn": isbn,
            "title": item.get("title", ""),
            "author": item.get("author", ""),
            "publisher": item.get("publisher", ""),
            "published_date": item.get("pubDate") or None,
            "cover_url": item.get("cover", ""),
            "category": item.get("categoryName", ""),
            "regular_price": item.get("priceStandard") or None,
            "description": item.get("description", "")
        })

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)