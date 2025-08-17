from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import APIException, ValidationError, NotAuthenticated, PermissionDenied
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    # 기본 예외 처리
    response = exception_handler(exc, context)

    # 예외가 처리되지 않은 경우
    if response is None:
        if isinstance(exc, ObjectDoesNotExist):
            return Response(
                {"isSuccess": False, "message": "요청한 객체를 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND
            )
        msg = str(exc) if settings.DEBUG else "서버 오류가 발생했습니다."
        return Response(
            {"isSuccess": False, "message": msg, "code": "COMMON_500"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    code = getattr(exc, 'default_code', exc.__class__.__name__)
    if isinstance(exc, ValidationError):
        return Response(
            {"isSuccess": False, "message": exc.detail, "code": "VALIDATION_400"},
            status=status.HTTP_400_BAD_REQUEST
        )
    if isinstance(exc, NotAuthenticated):
        return Response(
            {"isSuccess": False, "message": "인증이 필요합니다.", "code": "AUTH_401"},
            status=status.HTTP_401_UNAUTHORIZED
        )
    if isinstance(exc, PermissionDenied):
        return Response(
            {"isSuccess": False, "message": "권한이 없습니다.", "code": "AUTH_403"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # 일반 예외 처리
    detail = response.data.get('detail', str(exc))
    return Response(
        {"isSuccess": False, "message": detail, "code": code},
        status=response.status_code
    )