from django.urls import path
from .views import SurveyKeywordView

urlpatterns = [
    path("keywords/", SurveyKeywordView.as_view(), name="survey-keywords"),
]
