from django.urls import path
from .views import DonateBookLookUpAPIView, BookSearchAPIView

urlpatterns = [
    path("donate/", DonateBookLookUpAPIView.as_view(), name="book-donate"),
    path("search/", BookSearchAPIView.as_view(), name="book-search"),
    
]
