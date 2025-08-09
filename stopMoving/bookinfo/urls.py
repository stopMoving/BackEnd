from django.urls import path
from .views import BookLookUpAPIView

urlpatterns = [
    path("lookup/", BookLookUpAPIView.as_view(), name="book-lookup"),
]
