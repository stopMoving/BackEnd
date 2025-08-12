# libraryapp/urls.py
from django.urls import path
from .views import LibraryDetailAPIView

urlpatterns = [
    path("libraries/<int:library_id>/", LibraryDetailAPIView.as_view(), name="library-detail"),
]