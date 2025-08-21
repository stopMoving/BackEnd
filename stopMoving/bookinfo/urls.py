from django.urls import path
from .views import DonateBookLookUpAPIView, BookSearchAPIView, BookListView

urlpatterns = [
    path("donate/", DonateBookLookUpAPIView.as_view(), name="book-donate"),
    path("search/", BookSearchAPIView.as_view(), name="book-search"),
    path("list/", BookListView.as_view(), name="book-list"),
    # path("bulk/", BookInfoBulkAPIView.as_view(), name="bookinfo-bulk")
    
]
