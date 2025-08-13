from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import SurveyRequestSerializer, SurveyResultSerializer
from .services import run_survey_and_save
# Create your views here.

# 설문 처리 API
# 입력: isbns 배열(사용자가 선택한 3개)
# 출력: 추출 키워드 4~5개 + 사용자 벡터(list[float])
class SurveyKeywordView(APIView):
    
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="설문 → 키워드/사용자 벡터 생성",
        request_body=SurveyRequestSerializer,
        responses={200: SurveyResultSerializer},
        operation_description="선택한 3권의 ISBN을 바탕으로 키워드 4~5개를 추출하고, "
                              "키워드 임베딩 평균으로 사용자 취향 벡터를 생성/저장합니다."
    )
    def post(self, request):
        ser = SurveyRequestSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        isbns = ser.validated_data["isbns"]
        keywords, uvec = run_survey_and_save(request.user, isbns, top_k=5)
        out = {"keywords": keywords, "user_vector": uvec, "saved": True}
        return Response(SurveyResultSerializer(out).data, status=200)
