from django.urls import path
from .views import ExtractKeywordsView, RecommendView

urlpatterns = [
    path('keywords/', ExtractKeywordsView.as_view(), name='extract-keywords'),
    path('recommendations/', RecommendView.as_view(), name="recommendations")
]
