# books/urls.py
from django.urls import path
from .views import PickupAPIView, DonationAPIView, BookDetailAPIView, PickUpBookDetailAPIView

urlpatterns = [
    path("pickup/", PickupAPIView.as_view(), name="books-pick"),
    path("donate/", DonationAPIView.as_view(), name="books-donate"),
    path("by-isbn/<str:isbn>/",BookDetailAPIView.as_view(), name="books-detail"),
    path("pickup/detail/",PickUpBookDetailAPIView.as_view(), name="pickUpBooks-detail"),
]
