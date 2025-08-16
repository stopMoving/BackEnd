from django.urls import path
from .views import ExtractKeywordsView

urlpatterns = [
    path('keywords/', ExtractKeywordsView.as_view(), name='extract-keywords'),
]
