from django.urls import path
from .views import UserProfileView, MyDonatedBooksView, MyPurchasedBooksView, MyLibraryListAPIView, MyLibraryModifyAPIView, UserImageUploadView, UserImageView

urlpatterns = [
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('donated-books/', MyDonatedBooksView.as_view(), name='my-donated-books'),
    path('purchased-books/', MyPurchasedBooksView.as_view(), name='my-purchased-books'),
    path('my-libraries/modify/', MyLibraryModifyAPIView.as_view(), name='my-library-modify'),
    path('my-libraries/list/', MyLibraryListAPIView.as_view(), name='my-libraries-list'),
    path('upload/<int:user_id>/', UserImageUploadView.as_view(), name='image-upload'),
    path('image/<int:user_id>/', UserImageView.as_view(), name='image'),
]
