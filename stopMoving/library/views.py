from django.shortcuts import get_object_or_404, render

# Create your views here.
# 도서관 정보 조회 api
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .serializer import LibraryHoldingItemSerializer, LibraryInfoSerializer, LibraryNameSerializer, LibraryDetailSerializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Library, LibraryImage
from books.models import Book
from bookinfo.models import BookInfoLibrary, BookInfo
from .exceptions import LibraryNotFound, BookNotFound
from django.core.files.storage import default_storage  
from .serializer import ImageSerializer
from django.conf import settings
import boto3
from bookinfo.serializers import BookSummarySerializer
from .services import preference_books_per_lib
from rest_framework.permissions import IsAuthenticated

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
            BookInfoLibrary.objects
            .filter(library_id=library.id, status="AVAILABLE")
            .select_related("isbn") 
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

class LibraryListAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="전체 도서관 목록 조회",
        responses={200:"성공"}
    )
    def get(self, request):
        qs = Library.objects.all().only("id", "name") # 사이드탭: id랑 이름만 표시
        serializer = LibraryNameSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class LibraryImageUploadView(APIView):
    def post(self, request, library_id):
        lib = get_object_or_404(Library, pk=library_id)

        if 'image' not in request.FILES:
            return Response({"error": "No image file"}, status=status.HTTP_400_BAD_REQUEST)

        image_file = request.FILES['image']

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )

        # S3에 파일 저장
        file_path = f"uploads/{image_file.name}"
        # S3에 파일 업로드
        try:
            s3_client.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=file_path,
                Body=image_file.read(),
                ContentType=image_file.content_type,
            )
        except Exception as e:
            return Response({"error": f"S3 Upload Failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 업로드된 파일의 URL 생성
        image_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{file_path}"

        # DB에 저장
        image_instance = LibraryImage.objects.create(
            library=lib,
            image_url=image_url)
        
        serializer = ImageSerializer(image_instance)
        lib.library_image_url = image_url
        lib.save(update_fields=["library_image_url"])


        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
class LibraryDetailView(APIView):
    permission_classes = [permissions.AllowAny]  # 공개면
    def get(self, request, library_id):
        lib = get_object_or_404(Library, pk=library_id)
        return Response(LibraryDetailSerializer(lib).data)


        return Response(serializer.data, status=status.HTTP_201_CREATED)

class LibraryRecommendationView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, library_id: int):
        # 1) Library 존재 확인
        library = Library.objects.filter(pk=library_id).first()
        if not library:
            raise LibraryNotFound
        
        # 2) 책 없음 → 404 커스텀
        if not BookInfoLibrary.objects.filter(library_id=library.id, status="AVAILABLE").exists():
            raise BookNotFound
        
        # 3) 추천 책 isbn 목록으로
        isbn_list = preference_books_per_lib(user=request.user, lib_id=library_id)
        
        books_by_isbn = BookInfo.objects.filter(isbn__in=isbn_list)\
                                        .only("isbn", "title", "author", "cover_url", "category")\
                                        .in_bulk(field_name="isbn")
        
        results = []
        for isbn in isbn_list:
            bi = books_by_isbn.get(isbn)
            if not bi:
                continue
            results.append({
                "isbn": bi.isbn,
                "title": bi.title,
                "author": bi.author,
                "cover_url": bi.cover_url,
                "category": bi.category
            })
        
        response_data = {"library": library_id, "results": results}
        return Response(response_data, status=status.HTTP_200_OK)

