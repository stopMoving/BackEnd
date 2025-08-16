import time
import requests
from django.conf import settings

BASE = "http://www.aladin.co.kr/ttb/api"
TTBKEY = settings.API_KEY
COMMON_PARAMS = {
    "ttbkey": TTBKEY,
    "output": "JS",
    "Version": "20131101"
}

# get 요청을 위한 헬퍼 함수
def _get(url, params, timeout=20):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

# 상품 리스트 API
def get_booklist(
    query_type: str,
    search_target: str = "Book",
    start: int = 1,
    max_results: int = 100,
    category_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
    week: int | None = None,
):
    params = {
        **COMMON_PARAMS,
        "QueryType": query_type,
        "SearchTarget": search_target,
        "start": start,
        "MaxResults": max_results,
    }
    if category_id is not None:
        params["CategoryId"] = category_id
    # Bestseller 과거 주차 조회용 파라미터
    if year is not None:
        params["Year"] = year
    if month is not None:
        params["Month"] = month
    if week is not None:
        params["Week"] = week

    return _get(f"{BASE}/ItemList.aspx", params)

# 상품 상세 조회 API
def item_lookup(isbn: str):
    params = {
        **COMMON_PARAMS,
        "ItemIdType": "ISBN13" if len(isbn) == 13 else "ISBN",
        "ItemId": isbn
    }
    return _get(f"{BASE}/ItemLookUp.aspx", params)
import time
import requests
from django.conf import settings

BASE = "http://www.aladin.co.kr/ttb/api"
TTBKEY = settings.API_KEY
COMMON_PARAMS = {
    "ttbkey": TTBKEY,
    "output": "js",
    "Version": "20131101"
}

# get 요청을 위한 헬퍼 함수
def _get(url, params, timeout=20):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

# 상품 리스트 API
def get_booklist(query_type: str, search_target="Book"):
    params = {
        **COMMON_PARAMS,
        "QueryType": query_type,
        "SearchTarget": search_target
    }
    return _get(f"{BASE}/ItemList.aspx", params)

# 상품 상세 조회 API
def item_lookup(isbn: str):
    params = {
        **COMMON_PARAMS,
        "ItemIdType": "ISBN13" if len(isbn) == 13 else "ISBN",
        "ItemId": isbn
    }
    return _get(f"{BASE}/ItemLookUp.aspx", params)