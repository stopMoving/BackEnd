# library/exceptions.py
# library 앱의 커스텀 예외 처리
from rest_framework.exceptions import APIException

class LibraryNotFound(APIException):
    status_code = 404
    default_detail = "도서관을 찾을 수 없습니다."
    default_code = "LIBRARY_404"

class BookNotFound(APIException):
    status_code = 404
    default_detail = "해당 도서관에 구매 가능한(AVAILABLE) 도서가 없습니다."
    default_code = "BOOK_404"