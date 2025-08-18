from django.shortcuts import get_object_or_404, render
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, permissions

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from config.responses import empty_list
from .serializers import UserProfileSerializer, UserBookSerializer, MyLibraryModifySerializer
from library.serializer import LibraryNameSerializer
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

# '내 도서관' 등록/해제 
class MyLibraryModifyAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
            operation_description="내 도서관 토글(클릭 시: 없으면 추가, 있으면 제거)",
            request_body=MyLibraryModifySerializer,
            responses={
                200: MyLibraryModifySerializer(),
                400: "잘못된 요청",
                404: "해당 도서관 없음",
            }
    )
    def post(self, request):
        serializer = MyLibraryModifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        library_id = serializer.validated_data["library_id"]
        
        # 도서관 존재하는지 검증
        Library.objects.get(id=library_id)

        # UserInfo 검증
        UserInfo.objects.get(user=request.user)

        with transaction.atomic():
            ui = UserInfo.objects.select_for_update().get(user=request.user)
            ids = list(ui.my_lib_ids or [])
            before_in = library_id in ids

            if before_in:
                ids = [i for i in ids if i != library_id]
                result_action = "removed"
            else:
                ids.append(library_id)
                result_action = "added"

            ui.my_lib_ids = ids
            ui.save(update_fields=["my_lib_ids"])

        after_in = library_id in ids
        return Response(
            {"action": result_action, "in_my_lib": after_in, "my_lib_ids": ids},
            status=status.HTTP_200_OK,
        )

# 내 도서관 표시(사이드탭)
class MyLibraryListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="사이드바용 내 도서관 목록 조회",
    )
    def get(self, request):
        ui = UserInfo.objects.get(user=request.user)
        ids = ui.my_lib_ids or []
        if not ids:
            return Response({"libraries": []}, status=status.HTTP_200_OK)
        
        # 저장한 순서대로 반환
        qs = Library.objects.filter(id__in=ids).only("id", "name")
        by_id = {lib.id: lib for lib in qs}
        ordered = [by_id[i] for i in ids if i in by_id]

        data = LibraryNameSerializer(ordered, many=True).data
        return Response({"libraries": data}, status=status.HTTP_200_OK)