# bookinfo/services.py
import requests, re
from django.conf import settings
from .models import BookInfo
from .serializers import BookInfoUpsertSerializer

ALADIN_URL = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
ALADIN_TIMEOUT = 5

from decimal import Decimal, ROUND_FLOOR
DISCOUNT_RATE = Decimal("0.15")

def ensure_bookinfo(isbn: str):
    """
    DB에 BookInfo가 있으면 반환.
    없으면 알라딘 조회하여 저장 후 반환.
    실패하면 None.
    """
    isbn = re.sub(r"[-\s]", "", isbn or "")
    if not re.fullmatch(r"\d{10}|\d{13}", isbn): # 10자리 혹은 13자리만 허용
        return None

    # DB에 존재하면 return
    info = BookInfo.objects.filter(isbn=isbn).first()
    if info:
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

        ser = BookInfoUpsertSerializer(data={
            "isbn": isbn,
            "title": item.get("title", "") or "",
            "author": item.get("author", "") or "",
            "publisher": item.get("publisher", "") or "",
            "published_date": item.get("pubDate"),
            "cover_url": item.get("cover", "") or "",
            "category": item.get("categoryName", "") or "",
            "regular_price": price_std,
            "description": item.get("description", "") or "",
        })
        ser.is_valid(raise_exception=True)
        return ser.save()
    except Exception:
        return None

def get_sale_price(obj):
        # 정가 없으면 판매가는 고정 2000원
        if obj.regular_price is None:
            return 2000
        # 정가 있으면 85% 내림
        return int((Decimal(obj.regular_price) * DISCOUNT_RATE).to_integral_value(rounding=ROUND_FLOOR))