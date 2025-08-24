# libraryapp/urls.py
from django.urls import path
from .views import LibraryDetailAPIView, LibraryBooksAPIView, LibraryListAPIView, LibraryImageUploadView, LibraryRecommendationView, LibraryDetailView, LibraryBooksDetailView


urlpatterns = [
    path("detail/<int:library_id>/", LibraryDetailAPIView.as_view(), name="library-detail"), # 도서관 상세 정보 조회
    path('booklist/<int:library_id>/', LibraryBooksAPIView.as_view(), name='library-books'), # 도서관별 책 목록 조회
    path('list/', LibraryListAPIView.as_view(), name="library-list"), # 전체 도서관 목록 조회
    path('image/<int:library_id>/', LibraryDetailView.as_view(), name='image'), # 도서관 이미지 조회
    path('upload/<int:library_id>/', LibraryImageUploadView.as_view(), name='image-upload'),
    path('recommendations/<int:library_id>/', LibraryRecommendationView.as_view(), name='library-recommendation' ), # 도서관 보유 도서에서 책 추천
    path('book-detail/<int:library_id>/', LibraryBooksDetailView.as_view(), name='library-countbook'),

]