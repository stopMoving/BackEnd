# preferences/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .serializers import ISBNListSerializer
from bookinfo.models import BookInfo
from users.models import UserInfo, UserBook, Status
from accounts.models import User

# 새 엔진(사전 없이: KeyBERT × 전역IDF × 교집합가중)
from .services.keyword_extractor import extract_keywords_from_books
# 벡터
from preferences.services.embeddings import(
    load_vectorizer, serialize_sparse, deserialize_sparse, weighted_sum, l2_normalize
)
from preferences.services.recommend import cosine_topk, cosine_scores, apply_boosts, mmr_rerank
from django.conf import settings
from django.utils import timezone
import numpy as np
from scipy import sparse # csr 타입 위해 import
from books.services import CATEGORIES, preference_books_combined

SURVEY_MIN_BOOKS = 3
CATEGORIES_SET = set(CATEGORIES)

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

        # 설문조사 완료 후 설문조사 여부 수정
        user = request.user
        user.is_survey = True
        user.save(update_fields=["is_survey"])

        # 동일 TF-IDF 공간으로 설문 벡터화
        vec = load_vectorizer()
        survey_text = " ".join(keywords)
        sv = vec.transform([survey_text])
        ui.preference_vector_survey = serialize_sparse(sv)

        # 통합 =  α*survey + (1-α)*activity (활동 벡터는 아직 없는 상황)
        act = deserialize_sparse(ui.preference_vector_activity) if ui.preference_vector_activity else None
        combined = weighted_sum(sv, act, alpha = settings.RECOMMEND_ALPHA)
        # l2 정규화 추가
        combined = l2_normalize(combined)
        ui.preference_vector = serialize_sparse(combined if combined is not None else sv)

        ui.save(update_fields=[
            "preference_keyword",
            "survey_done",
            "last_survey_at",
            "preference_vector_survey",
            "preference_vector",
        ])

        # 사용자 db에 combined 기반 추천 책 isbn 목록 저장
        preference_books_combined(request.user)

        return Response({"keywords": keywords, "saved": True}, status=status.HTTP_200_OK)


def _csr_digest(csr: sparse.csr_matrix | None):
    if csr is None or getattr(csr, "nnz", 0) == 0:
        return {"nnz": 0, "sum": 0.0, "l2": 0.0}
    return {
        "nnz": int(csr.nnz),
        "sum": float(csr.sum()),
        "l2": float(np.sqrt((csr.data ** 2).sum())),
    }

class RecommendView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # mode = combined(default) | activity
        mode = (request.query_params.get("mode") or "combined").strip().lower()
        if mode not in ("combined", "activity"):
            mode = "combined"

        ui = UserInfo.objects.get(user=request.user)
        results = []
        cat = None

        if mode == "combined":
            preference_booklist = ui.preference_book_combined
        else:
            cat = (request.query_params.get("category") or "").strip()
            if cat not in CATEGORIES_SET:
                return Response(
                    {
                        "error_code": "INVALID_CATEGORY",
                        "messsage": f"허용되지 않은 category: {cat}",
                        "allowed": CATEGORIES,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raw = ui.preference_book_activity
            if isinstance(raw, dict):
                isbns = raw.get(cat, [])
            else:
                isbns = []
            preference_booklist = []
            for x in isbns:
                s = str(x)
                preference_booklist.append(s)
        
        for pb in preference_booklist:
            b=BookInfo.objects.get(isbn=pb)
            results.append({
                "isbn": b.isbn,
                "title": b.title,
                "author": b.author,
                "cover_url": b.cover_url,
                "category": b.category
            })
        
        response_data = {"mode": mode, "category": cat, "results": results}
        return Response(response_data, status=status.HTTP_200_OK)
