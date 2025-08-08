from django.shortcuts import render
from rest_framework_simplejwt.serializers import RefreshToken
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import *
from rest_framework import status

from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import logout

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# Create your views here.

# 회원가입
class RegisterView(APIView):
    @swagger_auto_schema(
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response(
                description="회원가입 성공",
                examples={
                    "application/json": {
                        "user": {
                            "username": "testuser",
                            "nickname": "테스트",
                            "password1": "password",
                            "password2": "password"
                        },
                        "message": "회원가입 성공!",
                        "token": {
                            "access_token": "access_token_value",
                            "refresh_token": "refresh_token_value"
                        }
                    }
                }
            ),
            400: "입력 유효성 오류"
        }
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        # 유효성 검사 
        if serializer.is_valid(raise_exception=True):
            
            # 유효성 검사 통과 후 객체 생성
            user = serializer.save()

            # user에게 refresh token 발급
            token = RefreshToken.for_user(user)
            refresh_token = str(token)
            access_token = str(token.access_token)

            res = Response(
                {
                    "user": serializer.data,
                    "message": "회원가입 성공!",
                    "token": {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                    }, 
                },
                status=status.HTTP_201_CREATED,
            )
            return res
        
# 로그인
class AuthView(APIView):
    @swagger_auto_schema(
        request_body=AuthSerializer,
        responses={
            200: openapi.Response(
                description="로그인 성공",
                examples={
                    "application/json": {
                        "user": {
                            "id": 1,
                            "username": "testuser",
                            "nickname": "테스트"
                        },
                        "message": "로그인 성공!",
                        "token": {
                            "access_token": "access_token_value"
                        }
                    }
                }
            ),
            400: "인증 실패"
        }
    )
    def post(self, request):
        serializer = AuthSerializer(data=request.data)
        
        # 유효성 검사
        if serializer.is_valid(raise_exception=True):
            user = serializer.validated_data['user']
            access_token = serializer.validated_data['access_token']
            refresh_token = serializer.validated_data['refresh_token']

            res = Response(
                {
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "nickname": user.nickname,
                    },
                    "message": "로그인 성공!",
                    "token": {
                        "access_token": access_token
                    }, 
                },
                status=status.HTTP_200_OK,
            )

            res.set_cookie(
                "access_token", 
                access_token, 
                httponly=True,
                secure=True,
                samesite="None" # 다른 Site에서 작성된 요청도 모두 쿠키를 담아서 보내줘도 상관없음
                )
            res.set_cookie(
                "refresh_token", 
                refresh_token, 
                httponly=True,
                secure=True,
                samesite="None"
                )
            return res
        
        # 유효성 검사 실패 시 오류 반환
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
# 로그아웃
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="로그아웃",
        responses={
            200: openapi.Response(
                description="로그아웃 성공",
                examples={"application/json": {"message": "로그아웃 성공!"}}
            ),
            401: "인증되지 않은 요청"
        }
    )

    def post(self, request):
        logout(request)
        return Response({"로그아웃 성공!"}, status=status.HTTP_200_OK)
    

