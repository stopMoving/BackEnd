from django.urls import path
from .views import BookLookUpAPIView, BookSearchAPIView

urlpatterns = [
    path("lookup/", BookLookUpAPIView.as_view(), name="book-lookup"),
    path("search/", BookSearchAPIView.as_view(), name="book-search"),
    
]
