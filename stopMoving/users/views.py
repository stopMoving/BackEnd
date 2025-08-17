from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from config.responses import empty_list
from .serializers import UserProfileSerializer, UserBookSerializer
from typing import List

from .models import UserInfo, Status, UserBook
from library.models import Library
from books.models import Book
from accounts.models import User
from bookinfo.models import BookInfo
from .exceptions import UserInfoNotFound, UserProfileSerializerError, NoDonatedBooks, NoPurchasedBooks

# Create your views here.
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="사용자 프로필 조회",
        responses={200: UserProfileSerializer()},
    )
    def get(self, request):
        user = request.user
        try:
            user_info = UserInfo.objects.get(user=user)
        except UserInfo.DoesNotExist:
            raise UserInfoNotFound()
        
        # 사용자 프로필 정보 직렬화
        profile_data = {
            "nickname": user.nickname,
            "points": user_info.points,
            "keywords": user_info.preference_keyword or []
        }

        try:
            serializer = UserProfileSerializer(instance=profile_data)
        except Exception:
            raise UserProfileSerializerError()
        
        return Response(serializer.data, status=status.HTTP_200_OK)

class MyDonatedBooksView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="사용자가 기증한 책 목록 조회",
        responses={200: UserBookSerializer(many=True)},
    )
    def get(self, request):
        qs = (
            UserBook.objects
            .filter(user=request.user, status=Status.DONATED)
            .select_related('book', 'book__library')
            .order_by('-created_at')
        )
        # 빈 결과 처리
        strict = request.query_params.get('strict', 'false').lower() == 'true'
        if not qs.exists():
            if strict:
                raise NoDonatedBooks()
            return empty_list("기증한 책이 없습니다.")
        
        return Response(UserBookSerializer(qs, many=True).data, status=status.HTTP_200_OK)
    
class MyPurchasedBooksView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="사용자가 구매한 책 목록 조회",
        responses={200: UserBookSerializer(many=True)},
    )
    def get(self, request):
        qs = (
            UserBook.objects
            .filter(user=request.user, status=Status.PURCHASED)
            .select_related('book', 'book__library')
            .order_by('-created_at')
        )
        # 빈 결과 처리
        strict = request.query_params.get('strict', 'false').lower() == 'true'
        if not qs.exists():
            if strict:
                raise NoPurchasedBooks()
            return empty_list("구매한 책이 없습니다.")
        
        return Response(UserBookSerializer(qs, many=True).data, status=status.HTTP_200_OK)