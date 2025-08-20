# bookinfo/services.py
import requests, re
from django.conf import settings
from .models import BookInfo
from .serializers import BookInfoUpsertSerializer
from preferences.services.embeddings import (
            load_vectorizer, ensure_vectorizer,
            build_text_from_bookinfo, serialize_sparse,
            build_text_from_meta
        )
from django.db import IntegrityError, transaction

ALADIN_URL = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
ALADIN_TIMEOUT = 5

from decimal import Decimal, ROUND_FLOOR
DISCOUNT_RATE = Decimal("0.15")

def ensure_bookinfo(isbn: str):
    """
    DB에 BookInfo가 있으면 반환(벡터 없으면 계산 -> 벡터만 저장).
    없으면 알라딘 조회 -> meat로 TF-IDF 벡터 먼저 계산 -> meta+vector DB에 저장.
    실패하면 None.
    """
    isbn = re.sub(r"[-\s]", "", isbn or "")
    if not re.fullmatch(r"\d{10}|\d{13}", isbn): # 10자리 혹은 13자리만 허용
        return None

    # DB에 존재하면 return
    info = BookInfo.objects.filter(isbn=isbn).first()
    if info:
        if not info.vector:
            _attach_vector_if_missing(info)
        return info

    if not getattr(settings, "API_KEY", None):
        return None

    params = {
        "ttbkey": settings.API_KEY,
        "itemIdType": "ISBN13" if len(isbn) == 13 else "ISBN",
        "ItemId": isbn,
        "output": "js",
        "Version": "20131101",
        "OptResult": "packing",
    }
    try:
        r = requests.get(ALADIN_URL, params=params, timeout=ALADIN_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        items = data.get("item") or []
        if not items:
            return None
        item = items[0]
        # 정가 캐스팅
        price_std = item.get("priceStandard")
        try:
            price_std = int(price_std) if price_std is not None else None
        except (TypeError, ValueError):
            price_std = None

        # meta dict(아직 db에 저장 전)
        meta = {
            "isbn": isbn,
            "title": item.get("title", "") or "",
            "author": item.get("author", "") or "",
            "publisher": item.get("publisher", "") or "",
            "published_date": item.get("pubDate"),
            "cover_url": item.get("cover", "") or "",
            "category": item.get("categoryName", "") or "",
            "regular_price": price_std,
            "description": item.get("description", "") or "",
        }

        # TF-IDF 벡터 계산
        try:
            vec = load_vectorizer()
        except Exception:
            # vectorizer.pkl이 없으면 최소 코퍼스로 1회 학습
            corpus = [build_text_from_bookinfo(bi) for bi in BookInfo.objects.all()[:5000]]
            if not corpus:
                corpus = [build_text_from_meta(meta)]
            vec = ensure_vectorizer(corpus)

        text = build_text_from_meta(meta)
        vector_json = serialize_sparse(vec.transform([text]))

        with transaction.atomic():
            ser = BookInfoUpsertSerializer(data=meta)
            ser.is_valid(raise_exception=True)
            info = ser.save()
            info.vector = vector_json
            info.save(update_fields=["vector"])
            return info
    except Exception:
        return None



# bookinfo 조회했는데 vector 칸만 비어있을 때 사용
def _attach_vector_if_missing(info: BookInfo) -> None:
    if info.vector:
        return
    try:
        try:
            vec = load_vectorizer()
        except Exception:
            corpus = [build_text_from_bookinfo(bi) for bi in BookInfo.objects.all()[:5000]]
            if not corpus:
                corpus = [build_text_from_bookinfo(info)]
            vec = ensure_vectorizer(corpus)

        text = build_text_from_bookinfo(info)
        info.vector = serialize_sparse(vec.transform[text])
        info.save(update_fields=["vector"])
    except Exception:
        pass
      
def get_sale_price(obj):
        # 정가 없으면 판매가는 고정 2000원
        if obj.regular_price is None:
            return 2000
        # 정가 있으면 85% 내림
        return int((Decimal(obj.regular_price) * DISCOUNT_RATE).to_integral_value(rounding=ROUND_FLOOR))

