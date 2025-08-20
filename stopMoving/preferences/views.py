# preferences/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .serializers import ISBNListSerializer
from bookinfo.models import BookInfo
from users.models import UserInfo

# 새 엔진(사전 없이: KeyBERT × 전역IDF × 교집합가중)
from .services.keyword_extractor import extract_keywords_from_books
# 벡터
from preferences.services.embeddings import(
    load_vectorizer, serialize_sparse, deserialize_sparse, weighted_sum
)
from django.conf import settings
from django.utils import timezone

SURVEY_MIN_BOOKS = 5

class ExtractKeywordsView(APIView):
    permission_classes = [IsAuthenticated]  # 회원가입 후 바로 액세스 토큰으로 인증

    def post(self, request):
        ser = ISBNListSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        isbns = ser.validated_data["isbns"]

        # 입력 개수 강제
        if len(isbns) < SURVEY_MIN_BOOKS:
            return Response(
                {"error": f"최소 {SURVEY_MIN_BOOKS}권의 ISBN이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 필요한 필드만 조회
        rows = list(
            BookInfo.objects
            .filter(isbn__in=isbns)
            .values("isbn", "title", "author", "category", "description")
        )

        if len(rows) < SURVEY_MIN_BOOKS:
            found = {r["isbn"] for r in rows}
            missing = [i for i in isbns if i not in found]
            return Response(
                {"error": f"요청한 {SURVEY_MIN_BOOKS}개 ISBN 중 {len(missing)}개를 찾지 못했습니다.",
                 "missing_isbns": missing},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 1) 키워드 추출
        # 새 엔진 호출 (한 단어 키워드, 전역IDF + 교집합 가중)
        keywords = extract_keywords_from_books(rows, top_n=4)
        if not keywords:
            return Response({"error": "키워드를 추출하지 못했습니다."},
                            status=status.HTTP_400_BAD_REQUEST)
        
        # 2) 사용자 UserInfo에 저장 + 벡터화
        ui, _ = UserInfo.objects.get_or_create(user=request.user)
        ui.preference_keyword = keywords
        ui.survey_done = True
        ui.last_survey_at = timezone.now()

        # 동일 TF-IDF 공간으로 설문 벡터화
        vec = load_vectorizer()
        survey_text = "".join(keywords)
        sv = vec.transform([survey_text])
        ui.preference_vector_survey = serialize_sparse(sv)

        # 통합 =  α*survey + (1-α)*activity (활동 벡터는 아직 없는 상황)
        act = deserialize_sparse(ui.preference_vector_activity) if ui.preference_vector_activity else None
        combined = weighted_sum(sv, act, alpha = settings.RECOMMEND_ALPHA)
        ui.preference_vector = serialize_sparse(combined if combined is not None else sv)

        ui.save(update_fields=[
            "preference_keyword",
            "survey_done",
            "last_survey_at",
            "preference_vector_survey",
            "preference_vector",
        ])

        return Response({"keywords": keywords, "saved": True}, status=status.HTTP_200_OK)
