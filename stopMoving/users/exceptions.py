# users/exceptions.py
# users 앱의 커스텀 예외 처리
from rest_framework.exceptions import APIException

class UserInfoNotFound(APIException):
    status_code = 404
    default_detail = "사용자 정보를 찾을 수 없습니다."
    default_code = "USER_INFO_404"

class UserProfileSerializerError(APIException):
    status_code = 500
    default_detail = "사용자 프로필 직렬화 오류가 발생했습니다"
    default_code = "USER_PROFILE_500"

class NoDonatedBooks(APIException):
    status_code = 404
    default_detail = "기증한 책이 없습니다."
    default_code = "DONATION_404"

class NoPurchasedBooks(APIException):
    status_code = 404
    default_detail = "구매한 책이 없습니다."
    default_code = "PURCHASE_404"