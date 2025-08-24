from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import OuterRef, Subquery
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, permissions

from drf_yasg.utils import swagger_auto_schema

from config.responses import empty_list
from .serializers import UserProfileSerializer, UserBookSerializer, MyLibraryModifySerializer
from library.serializer import LibraryNameSerializer

from .models import UserInfo, Status, UserBook, UserImage
from library.models import Library
from accounts.models import User
from .exceptions import UserInfoNotFound, UserProfileSerializerError, NoDonatedBooks, NoPurchasedBooks
from django.core.files.storage import default_storage  
from .serializers import ImageSerializer, UserDetailSerializer
from django.conf import settings
import boto3

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
            "keywords": user_info.preference_keyword or [],
            "user_image_url": user_info.user_image_url
        }

        try:
            serializer = UserProfileSerializer(profile_data)
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
        library_name_sq = Library.objects.filter(id=OuterRef('library_id')).values('name')

        qs = (
            UserBook.objects
            .filter(user=request.user, status=Status.DONATED)
            .select_related('bookinfo')
            .annotate(library_name=Subquery(library_name_sq))
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
        library_name_sq = Library.objects.filter(id=OuterRef('library_id')).values('name')
        qs = (
            UserBook.objects
            .filter(user=request.user, status=Status.PURCHASED)
            .select_related('bookinfo')
            .annotate(library_name=Subquery(library_name_sq))
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
    

class UserImageUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)

        if request.user.id != user.id and not request.user.is_staff:
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        
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
        image_instance = UserImage.objects.create(
            user_id=user_id,
            image_url=image_url)
        serializer = ImageSerializer(image_instance)

        userinfo = UserInfo.objects.filter(user_id=user_id).first()
        userinfo.user_image_url = image_url 
        userinfo.save(update_fields=["user_image_url"])

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
class UserImageView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, user_id):
        userinfo = get_object_or_404(UserInfo, user__id=user_id)

        return Response(UserDetailSerializer(userinfo).data)