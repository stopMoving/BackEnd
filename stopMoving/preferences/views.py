# preferences/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .serializers import ISBNListSerializer
from bookinfo.models import BookInfo
from users.models import UserInfo

# 새 엔진(사전 없이: KeyBERT × 전역IDF × 교집합가중)
from .services.keyword_extractor import extract_keywords_from_books


class ExtractKeywordsView(APIView):
    permission_classes = [AllowAny]  # 비로그인도 사용하려면

    def post(self, request):
        ser = ISBNListSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        isbns = ser.validated_data["isbns"]

        # 필요한 필드만 조회
        rows = list(
            BookInfo.objects
            .filter(isbn__in=isbns)
            .values("isbn", "title", "author", "category", "description")
        )

        if len(rows) < 3:
            found = {r["isbn"] for r in rows}
            missing = [i for i in isbns if i not in found]
            return Response(
                {"error": f"요청한 3개 ISBN 중 {len(missing)}개를 찾지 못했습니다.",
                 "missing_isbns": missing},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 새 엔진 호출 (한 단어 키워드, 전역IDF + 교집합 가중)
        keywords = extract_keywords_from_books(rows, top_n=4)
        if not keywords:
            return Response({"error": "키워드를 추출하지 못했습니다."},
                            status=status.HTTP_400_BAD_REQUEST)

        # (옵션) 로그인 사용자면 최신 취향 저장
        if request.user.is_authenticated:
            ui, _ = UserInfo.objects.get_or_create(user=request.user)
            ui.preference_keyword = keywords
            ui.survey_done = True
            ui.save(update_fields=["preference_keyword", "survey_done"])

        return Response({"keywords": keywords}, status=status.HTTP_200_OK)
