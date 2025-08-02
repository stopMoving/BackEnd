from django.shortcuts import render
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
# Create your views here.

class BookLookUpAPIView(APIView):
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