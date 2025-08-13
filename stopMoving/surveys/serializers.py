from rest_framework import serializers

# 설문 요청: 사용자가 고른 ISBN 3개
class SurveyRequestSerializer(serializers.Serializer):
    isbns = serializers.ListField(
        child=serializers.CharField(max_length=13, min_length=10),
        min_length=3, max_length=3
    )

# 설문 응답: 키워드 + 사용자 벡터
class SurveyResultSerializer(serializers.Serializer):
    keywords = serializers.ListField(child=serializers.CharField())
    user_vector = serializers.ListField(child=serializers.FloatField())
    saved = serializers.BooleanField()
