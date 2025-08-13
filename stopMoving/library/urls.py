# libraryapp/urls.py
from django.urls import path
from .views import LibraryDetailAPIView, LibraryBooksAPIView

urlpatterns = [
    path("detail/<int:library_id>/", LibraryDetailAPIView.as_view(), name="library-detail"), # 도서관 상세 정보 조회
    path('booklist/<int:library_id>/', LibraryBooksAPIView.as_view(), name='library-books'), # 도서관별 책 목록 조회
]