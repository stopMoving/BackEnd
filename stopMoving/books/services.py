from django.conf import settings
from django.db.models import Q
from requests import Response, request
from preferences.services.embeddings import deserialize_sparse, l2_normalize
from preferences.services.recommend import apply_boosts, cosine_scores, mmr_rerank
from users.models import UserBook, UserInfo
from bookinfo.models import BookInfo
from rest_framework import status
import numpy as np

CATEGORIES = ["소설/시/희곡", "만화", "어린이", "인문학", "에세이", "수험서/자격증", "경제경영", "과학"]

def preference_books_combined(user):
    mode = "combined"
    ui = UserInfo.objects.get(user=user)
    vec_json = ui.preference_vector
    user_vec = deserialize_sparse(vec_json)
    if user_vec is None or getattr(user_vec, "nnz", 0) == 0:
        return Response({"mode": mode, "results": []}, status=status.HTTP_200_OK)

    # 로딩 후 정규화(안전)
    user_vec = l2_normalize(user_vec)

    # 본인이 기증/수령한 책 제외
    exclude_isbns = set(
        UserBook.objects.filter(user=user)
        .values_list("bookinfo_id", flat=True)
    )

    # 후보군 로드
    items, bad_isbns, bad_shapes = [], [], 0
    exclude_bookinfos = BookInfo.objects.exclude(isbn__in=exclude_isbns).exclude(vector__isnull=True).iterator()
    for bi in exclude_bookinfos:
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
    use_div = True
    pool = int(getattr(settings, "RECOMMEND_MMR_POOL", 100))
    lam = float(getattr(settings, "RECOMMEND_MMR_LAMBDA", 0.3))

    if use_div:
        sel_idx = mmr_rerank(M, boosted, k=5, pool=pool, lam=lam)
        ordered_isbns = [cleaned[i][0] for i in sel_idx]            # ← MMR 순서 보존
    else:
        idx = np.argsort(-boosted)[:5]
        ordered_isbns = [cleaned[i][0] for i in idx]
        
    # userinfo의 preference_booklist에 isbn 리스트 저장
    ui.preference_book_combined = list(ordered_isbns)
    ui.save(update_fields=["preference_book_combined"])

def preference_books_activity(user, k=5):
    mode = "activity"
    ui = UserInfo.objects.get(user=user)
    vec_json = ui.preference_vector_activity
    user_vec = deserialize_sparse(vec_json)
    if user_vec is None or getattr(user_vec, "nnz", 0) == 0:
        return Response({"mode": mode, "results": []}, status=status.HTTP_200_OK)

    # 로딩 후 정규화(안전)
    user_vec = l2_normalize(user_vec)

    # 본인이 기증/수령한 책 제외
    exclude_isbns = set(
        UserBook.objects.filter(user=user)
        .values_list("bookinfo_id", flat=True)
    )

    # 후보군 로드
    items, bad_isbns, bad_shapes = [], [], 0
    exclude_bookinfos = BookInfo.objects.exclude(isbn__in=exclude_isbns).exclude(vector__isnull=True).iterator()
    for bi in exclude_bookinfos:
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
    # 최근 N권 평균 벡터
    n = getattr(settings, "RECOMMEND_RECENT_N", 3)
    recent_books = (UserBook.objects
                    .filter(user=user)
                    .order_by("-created_at")
                    .select_related("bookinfo")[:n])
    vs = []
    for ub in recent_books:
        bv = deserialize_sparse(getattr(ub.bookinfo, "vector", None))
        if bv is not None and getattr(bv, "nnz", 0) > 0:
            vs.append(bv)
    if vs:
        s = vs[0].copy()
        for v in vs[1:]:
            s = s + v
        recent_vec = l2_normalize(s * (1.0 / len(vs)))

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
    use_div = True
    pool = int(getattr(settings, "RECOMMEND_MMR_POOL", 100))
    lam = float(getattr(settings, "RECOMMEND_MMR_LAMBDA", 0.3))

    wanted = len(CATEGORIES) * k
    k_global = min(wanted * 2, len(cleaned)) # 여유 버퍼(2배 정도)로 MMR 선택

    if use_div:
        sel_idx = mmr_rerank(M, boosted, k=k_global, pool=pool, lam=lam)
        ordered_isbns = [cleaned[i][0] for i in sel_idx]            # ← MMR 순서 보존
    else:
        idx = np.argsort(-boosted)[:k_global]
        ordered_isbns = [cleaned[i][0] for i in idx]

    # 이 형식으로 preference_book_activity에 저장
    target = {cat: [] for cat in CATEGORIES}
    used = set()

    # 선별된 bookinfo에 대해 isbn, category 저장
    all_isbns = [t[0] for t in cleaned]
    isbn_to_cat = dict(BookInfo.objects.filter(isbn__in=all_isbns).values_list("isbn", "category"))
    
    def topcat_of(isbn: str) -> str | None:
        return first_category(isbn_to_cat.get(isbn))
    
    # 1차) MMR 순서에서 카테고리별 k개까지 채우기
    filled = 0
    for isbn in ordered_isbns:
        tc = topcat_of(isbn)
        if not tc:
            continue
        if len(target[tc]) < k:
            target[tc].append(isbn)
            used.add(isbn)
            filled += 1
            if filled >= wanted:
                break
    
    # 2차) 점수 내림차순 전체에서 부족 카테고리만 같은 카테고리로 보충
    order_full_idx = np.argsort(-boosted)
    for cat in CATEGORIES:
        if len(target[cat]) >= k:
            continue
        for i in order_full_idx:
            isbn = cleaned[i][0]
            if isbn in used:
                continue
            if topcat_of(isbn) == cat:
                target[cat].append(isbn)
                used.add(isbn)
                if len(target[cat]) >= k:
                    break


    # userinfo의 preference_booklist에 isbn 리스트 저장
    ui.preference_book_activity= target
    ui.save(update_fields=["preference_book_activity"])
    
def first_category(long_cat: str, base: str = "국내도서"):
    for short_cat in CATEGORIES:
        prefix = f"{base}>{short_cat}"
        if long_cat.startswith(prefix):
            return short_cat
    return None