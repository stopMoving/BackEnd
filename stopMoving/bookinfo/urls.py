from django.urls import path
from .views import DonateBookLookUpAPIView, BookSearchAPIView, BookInfoBulkAPIView

urlpatterns = [
    path("donate/", DonateBookLookUpAPIView.as_view(), name="book-donate"),
    path("search/", BookSearchAPIView.as_view(), name="book-search"),
    path("bulk/", BookInfoBulkAPIView.as_view(), name="bookinfo-bulk")
    
]
