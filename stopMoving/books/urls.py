# books/urls.py
from django.urls import path
from .views import PickBooksAPIView

urlpatterns = [
    path("pick/", PickBooksAPIView.as_view(), name="books-pick"),
]
