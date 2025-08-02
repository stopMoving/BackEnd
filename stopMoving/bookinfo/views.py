from django.shortcuts import render
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
# Create your views here.

class BookLookUpAPIView(APIView):
    @swagger_auto_schema(
        operation_description="ISBN으로 도서 정보 조회",
        manual_parameters=[
            openapi.Parameter(
                'isbn', openapi.IN_QUERY, description="ISBN 코드", type=openapi.TYPE_STRING, required=True
            )
        ],
        responses={200: '성공', 400: '잘못된 요청', 502: '외부 API 오류'}
    )
    def get(self, request):
        isbn = requests.query_params.get('isbn') # 프론트에서 넘겨주는 isbn
        if not isbn:
            return Response({"error": "ISBN이 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        
        url = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
        params = {
            "ttbkey": settings.ALADIN_API_KEY,
            "itemIdType": "ISBN13",
            "ItemId": isbn,
            "output": "js",
            "Version": "20131101"
        }

        try:
            res = requests.get(url, params=params, timeout=5)
            res.raise_for_status()
            data = res.json() #응답을 data에 저장
        except requests.RequestException as e:
            return Response({"error": f"API 요청 실패: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError:
            return Response({"error": "ISBN 결과 없음"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(data) # 필요 데이터 정해지면 해당 필드만 추출해서 사용