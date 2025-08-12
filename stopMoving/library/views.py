from django.shortcuts import get_object_or_404, render

# Create your views here.
# 도서관 정보 조회 api
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializer import LibraryInfoSerializer
from drf_yasg.utils import swagger_auto_schema
from .models import Library

class LibraryDetailAPIView(APIView):
    @swagger_auto_schema(
        operation_description="도서관 상세 정보 조회",
        responses={200: '성공', 404: '도서관 없음'}
    )
    def get(self, request, library_id: int):
        lib = get_object_or_404(Library, pk=library_id)
        serializer = LibraryInfoSerializer(lib)
        return Response(serializer.data, status=status.HTTP_200_OK)