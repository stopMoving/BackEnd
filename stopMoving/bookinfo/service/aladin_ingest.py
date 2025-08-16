from datetime import date
from typing import Iterable, Optional, Set, Dict, Any, Tuple
from core import aladin_client
from bookinfo.models import BookInfo
from django.db import transaction

QUERYTYPES = ["ItemNewAll", "ItemNewSpecial", "ItemEditorChoice", "Bestseller", "BlogBest"]

# 최근 몇 개월을 순회할지 (필요시 조절)
BESTSELLER_MONTHS_BACK = 12
BESTSELLER_WEEKS = [1, 2, 3, 4, 5]
BESTSELLER_MAX_PER_WEEK = 50  # 실사용에서 50 고정

# API 응답을 항상 리스트 형태로 정규화하여 반환
def _normalize_items(data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    items = data.get("item", [])
    if isinstance(items, dict):
        items = [items]
    return items # 항상 list[dict] 형태로 반환

# 주어진 쿼리 타입에 해당하는 ISBN 목록을 반환
def _collect_isbns_for_querytype(
    qt: str,
    search_target: str = "Book",
    category_id: Optional[int] = None,
    max_results_per_page: int = 100,
) -> Set[str]:
    isbns: Set[str] = set()

    # 1) 첫 호출에서 totalResults 파악
    first = aladin_client.get_booklist(
        qt,
        search_target=search_target,
        start=1,
        max_results=max_results_per_page,
        category_id=category_id,
    )
    total = int(first.get("totalResults", 0))  # 없으면 0으로 처리
    items = list(_normalize_items(first))
    for it in items:
        isbn13 = (it.get("isbn13") or "").strip()
        isbn10 = (it.get("isbn") or "").strip()
        if len(isbn13) == 13:
            isbns.add(isbn13)
        elif len(isbn10) in (10,):
            isbns.add(isbn10)

    if total <= max_results_per_page:
        return isbns

    # 2) 나머지 페이지 순회 (알라딘 리스트 총합 1,000개 한도)
    total = min(total, 1000)
    start = 1 + max_results_per_page
    while start <= total:
        data = aladin_client.get_booklist(
            qt,
            search_target=search_target,
            start=start,
            max_results=max_results_per_page,
            category_id=category_id,
        )
        items = list(_normalize_items(data))
        if not items:
            break
        for it in items:
            isbn13 = (it.get("isbn13") or "").strip()
            isbn10 = (it.get("isbn") or "").strip()
            if len(isbn13) == 13:
                isbns.add(isbn13)
            elif len(isbn10) in (10,):
                isbns.add(isbn10)
        start += max_results_per_page

    return isbns

def _last_n_months(n: int) -> list[Tuple[int, int]]:
    """
    오늘 기준 최근 n개월의 (year, month) 목록. 최근월부터 과거로.
    """
    today = date.today()
    y, m = today.year, today.month
    out: list[Tuple[int, int]] = []
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return out

# Bestseller를 여러 달 × 1~5주로 훑어서 최대한 많이 수집
# 같은 책이 여러 주에 걸쳐 중복될 수 있으므로 set으로 dedup
def _collect_bestseller_multiweeks(
    months_back: int = BESTSELLER_MONTHS_BACK,
    search_target: str = "Book",
) -> Set[str]:
    isbn_set: Set[str] = set()
    for (yy, mm) in _last_n_months(months_back):
        for ww in BESTSELLER_WEEKS:
            data = aladin_client.get_booklist(
                "Bestseller",
                search_target=search_target,
                start=1,
                max_results=BESTSELLER_MAX_PER_WEEK,
                year=yy,
                month=mm,
                week=ww,
            )
            items = list(_normalize_items(data))
            if not items:
                continue  # 해당 달/주에 데이터 없으면 스킵
            for item in items:
                isbn13 = (item.get("isbn13") or "").strip()
                isbn10 = (item.get("isbn") or "").strip()
                if len(isbn13) == 13:
                    isbn_set.add(isbn13)
                elif len(isbn10) == 10:
                    isbn_set.add(isbn10)
    return isbn_set

def _safe_slice(s: str | None, limit: int) -> str:
    s = (s or "").strip()
    return s[:limit]
      
# select -> update/insert 실행해야 하기 때문에 트랜잭션으로 실행
@transaction.atomic
def upsert_book_from_item(item: Dict[str, Any]) -> bool:
    isbn = (item.get("isbn13") or item.get("isbn")).strip()
    if not isbn or len(isbn) not in {10, 13}:
        return False
    
    title = item.get("title", "").strip()
    author = _safe_slice(item.get("author"), 255)
    publisher = item.get("publisher", "").strip()
    published_date = item.get("pubDate")
    cover_url = item.get("cover", "").strip()
    category = item.get("categoryName", "").strip()
    regular_price = item.get("priceStandard")
    description = item.get("description", "").strip()

    BookInfo.objects.update_or_create(
        isbn=isbn,
        defaults={
            "title": title,
            "author": author,
            "publisher": publisher,
            "published_date": published_date,
            "cover_url": cover_url,
            "category": category,
            "regular_price": regular_price,
            "description": description,
        }
    )
    return True

# 1) 각 쿼리타입으로 리스트 1회 호출 -> isbn 수집
# 2) 수집된 isbn으로 상세 조회 -> upsert
# run() 안에서: 타겟/카테고리 확장 루프 추가
def run(querytypes: Optional[Iterable[str]] | None=None, dry_run: bool = False) -> dict:
    qts = querytypes or QUERYTYPES
    all_isbns: Set[str] = set()

    # 국내도서만 검색(외국도서/ebook 등은 제외)
    search_targets = ["Book"]

    # 편집자 추천은 카테고리 필수 → 대표 카테고리 몇 개 루프
    editor_choice_categories = [1, 55889, 51311, 170]  # 예: 국내도서/외국도서/경제경영/IT모바일 등 (필요에 맞게 조정)

    for qt in qts:
        for st in search_targets:
            if qt == "Bestseller":
                # 과거 여러 주차까지 긁기
                all_isbns |= _collect_bestseller_multiweeks(
                    months_back=BESTSELLER_MONTHS_BACK,
                    search_target=st,
                )
            elif qt == "ItemEditorChoice":
                # 편집자 추천은 CategoryId 있어야 풍부함 — 필요시 대표 카테고리 루프 추가
                all_isbns |= _collect_isbns_for_querytype(qt, search_target=st, category_id=None)
            else:
                all_isbns |= _collect_isbns_for_querytype(qt, search_target=st)


    saved_count = 0
    for isbn in all_isbns:
        detail = aladin_client.item_lookup(isbn)
        items = list(_normalize_items(detail))
        if not items:
            continue
        if not dry_run:
            if upsert_book_from_item(items[0]):
                saved_count += 1

    return {
        "querytypes": qts,
        "isbn_count": len(all_isbns),
        "saved_count": saved_count
    }