from django.conf import settings
from django.db.models import F
from django.db import transaction
from django.utils.text import Truncator
from rest_framework.response import Response
from preferences.services.embeddings import deserialize_sparse, l2_normalize
from preferences.services.recommend import apply_boosts, cosine_scores, mmr_rerank
from users.models import UserBook, UserInfo
from bookinfo.models import BookInfo, BookInfoLibrary
from notification.models import Notification
from notification.service import push
from accounts.models import User
from rest_framework import status
import numpy as np

CATEGORIES = ["소설/시/희곡", "만화", "어린이", "인문학", "에세이", "수험서/자격증", "경제경영", "과학"]

# 도서관별로 분기하여 책 추천해주는 api
def preference_books_per_lib(user, lib_id: int):
    mode = "combined"
    ui = UserInfo.objects.get(user=user)
    vec_json = ui.preference_vector
    user_vec = deserialize_sparse(vec_json)
    if user_vec is None or getattr(user_vec, "nnz", 0) == 0:
        return Response({"results": []}, status=status.HTTP_200_OK)

    # 로딩 후 정규화(안전)
    user_vec = l2_normalize(user_vec)

    # 본인이 기증/수령한 책 제외
    exclude_isbns = set(
        UserBook.objects.filter(user=user)
        .values_list("bookinfo_id", flat=True)
    )

    # lib_id에 해당하는 도서관의 수령 가능한 책들만 가져오기
    lib_isbns = set(BookInfoLibrary.objects
                    .filter(library_id=lib_id, status="AVAILABLE")
                    .values_list("isbn", flat=True))

    # 후보군 로드
    cand_isbns = lib_isbns - exclude_isbns
    items = []
    book_qs = (
        BookInfo.objects.filter(isbn__in=cand_isbns)
        .exclude(vector__isnull=True).only("isbn", "vector").iterator()
    )
    for bi in book_qs:
        csr = deserialize_sparse(bi.vector)
        if csr is None or getattr(csr, "nnz", 0) > 0:
            items.append((bi.isbn, csr))

    # base scores
    cleaned, M, base_scores = cosine_scores(user_vec, items)
    if not cleaned:
        return Response({"results": []}, status=status.HTTP_200_OK)

    # 모드별 부스트용 벡터
    sv = deserialize_sparse(getattr(ui, "preference_vector_survey", None))
    recent_vec = None

    # 부스트 가중치 변경 가능
    survey_w = float(getattr(settings, "RECOMMEND_SURVEY_BOOST", 0.25))
    recent_w = float(getattr(settings, "RECOMMEND_RECENT_BOOST", 0.30))

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
    pool = int(getattr(settings, "RECOMMEND_MMR_POOL", 100))
    lam = float(getattr(settings, "RECOMMEND_MMR_LAMBDA", 0.3))

    sel_idx = mmr_rerank(M, boosted, k=5, pool=pool, lam=lam)
    ordered_isbns = [cleaned[i][0] for i in sel_idx]            # ← MMR 순서 보존
        
    return ordered_isbns