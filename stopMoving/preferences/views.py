# preferences/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .serializers import ISBNListSerializer
from bookinfo.models import BookInfo
from users.models import UserInfo, UserBook, Status

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
        vec_json = ui.preference_vector if mode == "combined" else ui.preference_vector_activity
        user_vec = deserialize_sparse(vec_json)
        if user_vec is None or getattr(user_vec, "nnz", 0) == 0:
            return Response({"mode": mode, "results": []}, status=status.HTTP_200_OK)

        # 로딩 후 정규화(안전)
        user_vec = l2_normalize(user_vec)

        # 본인이 기증/수령한 책 제외
        exclude_isbns = set(
            UserBook.objects.filter(user=request.user)
            .values_list("book__isbn__isbn", flat=True)
        )

        # 후보군 로드
        items, bad_isbns, bad_shapes = [], [], 0
        for bi in (BookInfo.objects
                   .exclude(isbn__in=exclude_isbns)
                   .exclude(vector__isnull=True)
                   .iterator()):
            csr = deserialize_sparse(bi.vector)
            if csr is None or getattr(csr, "nnz", 0) == 0:
                bad_isbns.append(bi.isbn)
                continue
            pair = (bi.isbn, csr)
            if not (isinstance(pair, (tuple, list)) and len(pair) == 2):
                bad_shapes += 1
                continue
            items.append(pair)

        # base scores
        cleaned, M, base_scores = cosine_scores(user_vec, items)
        if not cleaned:
            return Response({"mode": mode, "results": []}, status=status.HTTP_200_OK)

        # 모드별 부스트용 벡터
        sv = deserialize_sparse(getattr(ui, "preference_vector_survey", None))

        recent_vec = None
        if mode == "activity":
            # 최근 N권 평균 벡터
            n = getattr(settings, "RECOMMEND_RECENT_N", 3)
            recent_books = (UserBook.objects
                            .filter(user=request.user)
                            .order_by("-created_at")
                            .select_related("book__isbn")[:n])
            vs = []
            for ub in recent_books:
                bv = deserialize_sparse(getattr(ub.book.isbn, "vector", None))
                if bv is not None and getattr(bv, "nnz", 0) > 0:
                    vs.append(bv)
            if vs:
                s = vs[0].copy()
                for v in vs[1:]:
                    s = s + v
                recent_vec = l2_normalize(s * (1.0 / len(vs)))

        # 쿼리 파라미터로 부스트 가중치 변경 가능
        survey_w = float(request.query_params.get("survey_boost") or getattr(settings, "RECOMMEND_SURVEY_BOOST", 0.25))
        recent_w = float(request.query_params.get("recent_boost") or getattr(settings, "RECOMMEND_RECENT_BOOST", 0.30))

        boosted = apply_boosts(
            mode=mode,
            M=M,
            base_scores=base_scores,
            survey_vec=sv,
            recent_vec=recent_vec,
            survey_w=survey_w,
            recent_w=recent_w,
        )

        # MMR 리랭킹 (선택된 "순서" 그대로 결과에 반영)
        use_div = (request.query_params.get("diversity") or "1").strip().lower() in ("1", "true", "yes", "y")
        pool = int(request.query_params.get("pool") or getattr(settings, "RECOMMEND_MMR_POOL", 100))
        lam = float(request.query_params.get("lambda") or getattr(settings, "RECOMMEND_MMR_LAMBDA", 0.3))

        if use_div:
            sel_idx = mmr_rerank(M, boosted, k=5, pool=pool, lam=lam)
            ordered_isbns = [cleaned[i][0] for i in sel_idx]            # ← MMR 순서 보존
            ordered_scores = [float(boosted[i]) for i in sel_idx]
        else:
            idx = np.argsort(-boosted)[:5]
            ordered_isbns = [cleaned[i][0] for i in idx]
            ordered_scores = [float(boosted[i]) for i in idx]

        # 한 번에 가져오고, "선택된 순서"대로 결과 구성
        books_by_isbn = {b.isbn: b for b in BookInfo.objects.filter(isbn__in=ordered_isbns)}
        results = []
        for isbn, sc in zip(ordered_isbns, ordered_scores):
            b = books_by_isbn.get(isbn)
            if not b:
                continue
            results.append({
                "isbn": b.isbn,
                "title": b.title,
                "author": b.author,
                "cover_url": b.cover_url,
                "category": b.category,
                "score": round(sc, 6),
            })

        response_data = {"mode": mode, "results": results}

        # 디버깅 상세
        dbg = (request.query_params.get("debug") or "").strip().lower()
        if dbg in ("1", "true", "yes", "y"):
            # 원본 벡터 대비/코사인 유사도
            u_comb = deserialize_sparse(ui.preference_vector)
            u_act  = deserialize_sparse(ui.preference_vector_activity)
            def _cos(u, v):
                if u is None or v is None or getattr(u, "nnz", 0) == 0 or getattr(v, "nnz", 0) == 0:
                    return 0.0
                num = float((u @ v.T).toarray()[0, 0])
                du  = float(np.sqrt((u.data**2).sum()))
                dv  = float(np.sqrt((v.data**2).sum()))
                return num / (du*dv) if du > 0 and dv > 0 else 0.0
            response_data["debug"] = {
                "candidate_count": len(cleaned),
                "exclude_count": len(exclude_isbns),
                "mmr_pool": pool,
                "mmr_lambda": lam,
                "used_diversity": use_div,
                "used_vec_digest": _csr_digest(user_vec),
                "raw_combined_digest": _csr_digest(u_comb),
                "raw_activity_digest": _csr_digest(u_act),
                "combined_vs_activity_cosine": round(_cos(u_comb, u_act), 6),
                "survey_vec_used": bool(sv is not None and getattr(sv, "nnz", 0) > 0),
                "recent_vec_used": bool(recent_vec is not None and getattr(recent_vec, "nnz", 0) > 0),
                "survey_boost": survey_w,
                "recent_boost": recent_w,
            }
            if bad_isbns:
                response_data["debug"]["skipped_bad_vectors"] = bad_isbns[:20]
            if bad_shapes:
                response_data["debug"]["bad_shape_count"] = bad_shapes

        return Response(response_data, status=status.HTTP_200_OK)
