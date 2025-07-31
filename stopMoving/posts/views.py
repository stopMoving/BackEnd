from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
import logging

# 로깅 설정
logger = logging.getLogger(__name__)

# Create your views here.
# API 테스트를 위한 뷰
class Ping(APIView):
    def get(self, request):
        logger.info("Ping 호출")
        return Response({
            "status": 200,
            "message": "pong"
        })