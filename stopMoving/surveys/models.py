from django.conf import settings
from django.db import models

# 사용자 설문 제출 기록(선택한 책/결과 키워드/생성 벡터 저장)
class SurveyResponse(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    selected_isbns = models.JSONField()                   # ["979...", "978...", "979..."]
    extracted_keywords = models.JSONField(null=True, blank=True)
    generated_vector = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]
