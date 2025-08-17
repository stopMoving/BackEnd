from django.urls import path
from .views import UserProfileView, MyDonatedBooksView, MyPurchasedBooksView

urlpatterns = [
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('donated-books/', MyDonatedBooksView.as_view(), name='my-donated-books'),
    path('purchased-books/', MyPurchasedBooksView.as_view(), name='my-purchased-books'),
]
