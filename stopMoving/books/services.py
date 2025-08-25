from django.conf import settings
from django.db.models import F
from django.db import transaction
from django.utils.text import Truncator
from rest_framework.response import Response
from preferences.services.embeddings import deserialize_sparse, l2_normalize
from preferences.services.recommend import apply_boosts, cosine_scores, mmr_rerank
from users.models import UserBook, UserInfo
from bookinfo.models import BookInfo
from notification.models import Notification
from notification.service import push
from accounts.models import User
from rest_framework import status
import numpy as np

CATEGORIES = ["소설/시/희곡", "만화", "어린이", "인문학", "에세이", "수험서/자격증", "경제경영", "과학"]

def preference_books_combined(user, db_alias='default', k=5):
    try:
        ui = UserInfo.objects.using(db_alias).get(user=user)
    except UserInfo.DoesNotExist:
        return
    mode = "combined"

    user_vec = deserialize_sparse(getattr(ui, "preference_vector", None))
    if user_vec is None or getattr(user_vec, "nnz", 0) == 0:
        return
    
    # 로딩 후 정규화(안전)
    user_vec = l2_normalize(user_vec)

    # 본인이 기증/수령한 책 제외
    exclude_isbns = set(
        UserBook.objects.using(db_alias).filter(user=user)
        .values_list("bookinfo_id", flat=True)
    )

    # 후보군 로드
    items = []
    for bi in (BookInfo.objects.using(db_alias)
               .exclude(isbn__in=exclude_isbns)
               .exclude(vector__isnull=True).iterator()):
        csr = deserialize_sparse(bi.vector)
        if csr is None or getattr(csr, "nnz", 0) == 0:
            continue
        items.append((bi.isbn, csr))

    # base scores
    cleaned, M, base_scores = cosine_scores(user_vec, items)
    if not cleaned:
        return 
    
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
        sel_idx = mmr_rerank(M, boosted, k=k, pool=pool, lam=lam)
        ordered_isbns = [cleaned[i][0] for i in sel_idx]            # ← MMR 순서 보존
    else:
        idx = np.argsort(-boosted)[:5]
        ordered_isbns = [cleaned[i][0] for i in idx]
        
    # userinfo의 preference_booklist에 isbn 리스트 저장
    ui.preference_book_combined = ordered_isbns
    ui.save(update_fields=["preference_book_combined"])
    return None

def preference_books_activity(user, k=5, db_alias='default'):
    try:
        ui = UserInfo.objects.using(db_alias).get(user=user)
    except UserInfo.DoesNotExist:
        return
    mode = "activity"

    vec_json = ui.preference_vector_activity
    user_vec = deserialize_sparse(vec_json)
    if user_vec is None or getattr(user_vec, "nnz", 0) == 0:
        return 
    
    # 로딩 후 정규화(안전)
    user_vec = l2_normalize(user_vec)

    # 본인이 기증/수령한 책 제외
    exclude_isbns = set(
        UserBook.objects.using(db_alias)
        .filter(user=user)
        .values_list("bookinfo_id", flat=True)
    )

    # 후보군 로드
    items = []
    for bi in (BookInfo.objects.using(db_alias)
               .exclude(isbn__in=exclude_isbns)
               .exclude(vector__isnull=True).iterator()):
        csr = deserialize_sparse(bi.vector)
        if csr is None or getattr(csr, "nnz", 0) == 0:
            continue
        items.append((bi.isbn, csr))

    # base scores
    cleaned, M, base_scores = cosine_scores(user_vec, items)
    if not cleaned:
        return 
    
    # 모드별 부스트용 벡터
    sv = deserialize_sparse(getattr(ui, "preference_vector_survey", None))

    recent_vec = None
    # 최근 N권 평균 벡터
    n = getattr(settings, "RECOMMEND_RECENT_N", 3)
    recent_books = (UserBook.objects.using(db_alias)
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
    isbn_to_cat = dict(BookInfo.objects.using(db_alias)
                       .filter(isbn__in=all_isbns).values_list("isbn", "category"))
    
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
    return None
    
def first_category(long_cat: str | None, base: str = "국내도서"):
    if not long_cat:
        return None
    for short_cat in CATEGORIES:
        prefix = f"{base}>{short_cat}"
        if long_cat.startswith(prefix):
            return short_cat
    return None

# (isbn, csr) 리스트와 제목 맵 반환
def _load_book_vectors_for_isbns(isbns):
    items, title_of = [], {}
    for bi in (BookInfo.objects.filter(isbn__in=isbns)
               .only("isbn", "title", "vector").iterator()):
        csr = deserialize_sparse(getattr(bi, "vector", None))
        if csr is None or getattr(csr, "nnz", 0) == 0:
            continue
        items.append((bi.isbn, csr))
        title_of[bi.isbn]  = bi.title
    return items, title_of

# donated_isbns에 대해 취향 매칭되는 유저에게 notification 생성
# combined mode와 동일한 로직으로
@transaction.atomic
def preference_notification(donor_user, donated_isbns, k: int = 3, thresh: float = 0.15,
                            use_mmr: bool=True):
    mode = "combined"
    if not donated_isbns:
        return None
    
    # 기증된 책들
    isbns = sorted(set(str(x).strip() for x in donated_isbns))
    items, title_of = _load_book_vectors_for_isbns(isbns)
    if not items:
        return None
    
    # 여기에 알림 저장
    notifications = []

    # 기증자 제외한 유저들 가져옴(필요한 필드만)
    user_qs = (UserInfo.objects.exclude(user_id=donor_user.id)
               .only("user_id", "preference_vector", "preference_vector_survey")
               .select_related("user").iterator())
    
    # 유저별로 처리
    for ui in user_qs:
        # 유저 벡터 가져옴
        uvec = deserialize_sparse(ui.preference_vector)
        if uvec is None or getattr(uvec, "nnz", 0) == 0:
            continue
        uvec = l2_normalize(uvec)

        # 유저가 이미 기증/수령한 도서는 제외
        owned = set(UserBook.objects.filter(user_id=ui.user_id, bookinfo_id__in=isbns)
                    .values_list("bookinfo_id", flat=True))
        cand_items = [(isbn, csr) for (isbn, csr) in items if isbn not in owned]
        if not cand_items:
            continue

        # 사용자 벡터 - 기증된 책 벡터 비교
        cleaned, M, base_scores = cosine_scores(uvec, cand_items)
        if M is None or M.shape[0] == 0:
            continue

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
        pool = int(getattr(settings, "RECOMMEND_MMR_POOL", 50))
        lam = float(getattr(settings, "RECOMMEND_MMR_LAMBDA", 0.3))

        if use_mmr:
            try:
                sel_idx = mmr_rerank(M, boosted, k=k, pool=pool, lam=lam)
            except Exception:
                sel_idx = list(np.argsort(-boosted)[:k])
        else:
            sel_idx = list(np.argsort(-boosted)[:k])

        # 일정 점수 이상의 코사인 유사도 -> pick해서 알림 생성
        picks = []
        for i in sel_idx:
            score = float(boosted[i])
            if score >= thresh:
                picks.append((cleaned[i][0], score))
        if not picks:
            continue

        picks.sort(key=lambda x: x[1], reverse=True)
        chosen_isbns = [isbn for isbn, _ in picks][:k]
        chosen_titles = [title_of.get(z, "도서") for z in chosen_isbns]

        # 《 》로 감싼 표시용 문자열 생성 (안 길게 30자 정도로 자름)
        def wrap_title(s: str) -> str:
            inner = Truncator(s).chars(30)
            return f"\u300A{inner}\u300B"  # 《 ... 》

        wrapped = [wrap_title(t) for t in chosen_titles]
        
        for i in range(len(wrapped)):
            msg = f"《{wrapped[i]}》 이 방금 나눔됐어요!\n 놓치기 전에 데려가보세요."
            push(user=ui.user, type_="book_recommendation", message=msg)

            #《》