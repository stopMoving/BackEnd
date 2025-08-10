# books/urls.py
from django.urls import path
from .views import PickupAPIView, DonationAPIView

urlpatterns = [
    path("pick/", PickupAPIView.as_view(), name="books-pick"),
    path("donate/", DonationAPIView.as_view(), name="books-donate"),

]
