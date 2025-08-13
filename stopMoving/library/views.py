from django.shortcuts import get_object_or_404, render

# Create your views here.
# 도서관 정보 조회 api
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .serializer import LibraryHoldingItemSerializer, LibraryInfoSerializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Library
from books.models import Book
from .exceptions import LibraryNotFound, BookNotFound

class LibraryDetailAPIView(APIView):
    @swagger_auto_schema(
        operation_description="도서관 상세 정보 조회",
        responses={200: '성공', 404: '도서관 없음'}
    )
    def get(self, request, library_id: int):
        lib = get_object_or_404(Library, pk=library_id)
        serializer = LibraryInfoSerializer(lib)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class LibraryBooksAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="도서관의 책 목록 조회",
        manual_parameters=[ ],
        responses={
            200: "성공",
            400: "잘못된 요청",
            404: "도서관/도서 없음 (LIBRARY_404 / BOOK_404)",
        },
    )
    def get(self, request, library_id: int):
        # 1) 도서관 존재 확인 (없으면 404 커스텀)
        library = Library.objects.filter(pk=library_id).first()
        if not library:
            raise LibraryNotFound
        
        # 2) 상태가 AVAILABLE인 책만 필터링 + BookInfo 조인
        qs = (
            Book.objects
            .filter(library_id=library.id, status="AVAILABLE")  # 대문자 주의
            .select_related("isbn")  # Book.isbn(FK) → BookInfo
            .only(
                "id", "status",
                "isbn__isbn", "isbn__title", "isbn__author",
                "isbn__publisher", "isbn__cover_url"
            )
            .order_by("-id")
        )

        # 3) 책 없음 → 404 커스텀
        if not qs.exists():
            raise BookNotFound

        # 4) 직렬화 & 반환 (전체 목록 그대로)
        data = LibraryHoldingItemSerializer(qs, many=True).data
        return Response(data, status=status.HTTP_200_OK)