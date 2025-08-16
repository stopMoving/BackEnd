from typing import Iterable, Optional, Set, Dict, Any, Tuple
from core import aladin_client
from bookinfo.models import BookInfo
from django.db import transaction

QUERYTYPES = ["ItemNewAll", "ItemNewSpecial", "ItemEditorChoice", "Bestseller", "BlogBest"]

# API 응답을 항상 리스트 형태로 정규화하여 반환
def _normalize_items(data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    items = data.get("item", [])
    if isinstance(items, dict):
        items = [items]
    return items # 항상 list[dict] 형태로 반환

# 주어진 쿼리 타입에 해당하는 ISBN 목록을 반환
def _collect_isbns_for_querytype(qt: str) -> Set[str]:
    data = aladin_client.get_booklist(qt, search_target="Book")
    isbn_set: Set[str] = set()
    for item in _normalize_items(data):
        isbn13 = (item.get("isbn13") or "").strip()
        if len(isbn13) == 13:
            isbn_set.add(isbn13)
    return isbn_set
        
# select -> update/insert 실행해야 하기 때문에 트랜잭션으로 실행
@transaction.atomic
def upsert_book_from_item(item: Dict[str, Any]) -> bool:
    isbn = (item.get("isbn13") or item.get("isbn")).strip()
    if not isbn or len(isbn) not in {10, 13}:
        return False
    
    title = item.get("title", "").strip()
    author = item.get("author", "").strip()
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
def run(querytypes: Optional[Iterable[str]] | None=None, dry_run: bool = False) -> dict:
    qts = querytypes or QUERYTYPES
    all_isbns: Set[str] = set()

    for qt in qts:
        all_isbns |= _collect_isbns_for_querytype(qt)

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