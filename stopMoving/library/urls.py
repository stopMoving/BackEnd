# libraryapp/urls.py
from django.urls import path
from .views import LibraryDetailAPIView, LibraryBooksAPIView, LibraryListAPIView, LibraryImageUploadView

urlpatterns = [
    path("detail/<int:library_id>/", LibraryDetailAPIView.as_view(), name="library-detail"), # 도서관 상세 정보 조회
    path('booklist/<int:library_id>/', LibraryBooksAPIView.as_view(), name='library-books'), # 도서관별 책 목록 조회
    path('list/', LibraryListAPIView.as_view(), name="library-list"), # 전체 도서관 목록 조회
    path('upload/', LibraryImageUploadView.as_view(), name='image-upload') # 도서관 이미지 업로드 
]