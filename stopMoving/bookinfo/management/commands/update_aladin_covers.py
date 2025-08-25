import time
import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from bookinfo.models import BookInfo
from django.conf import settings

ALADIN_API = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"


def fetch_cover_big(isbn13: str) -> str | None:
    """알라딘 API에서 cover=big URL 얻기"""
    isbn = isbn13
    params = {
        "ttbkey": settings.API_KEY,  # ✅ settings에서 직접 사용
        "itemIdType": "ISBN13" if len(isbn) == 13 else "ISBN",
        "itemId": isbn,
        "cover": "big",
        "output": "js",
        "Version": "20131101",
        "OptResult": "packing",
    }
    r = requests.get(ALADIN_API, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    items = data.get("item") or data.get("items") or []
    if not items:
        return None
    return items[0].get("cover") or None


class Command(BaseCommand):
    help = "알라딘 API를 다시 호출해 BookInfo.cover_url을 cover=big으로 일괄 업데이트"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="처리할 최대 레코드 수(테스트용)")
        parser.add_argument("--only-missing", action="store_true", help="cover_url 비어있는 항목만 처리")
        parser.add_argument("--dry-run", action="store_true", help="DB에 저장하지 않고 어떤 변경이 일어날지만 출력")
        parser.add_argument("--sleep", type=float, default=0.2, help="요청 간 대기(초), API rate limit 회피용")

    def handle(self, *args, **opts):
        if not settings.API_KEY:
            self.stderr.write(self.style.ERROR("settings.API_KEY가 없습니다. settings.py 또는 환경변수를 확인하세요."))
            return

        qs = BookInfo.objects.all().only("isbn", "cover_url")
        if opts["only_missing"]:
            qs = qs.filter(cover_url__isnull=True) | qs.filter(cover_url="")

        if opts["limit"]:
            qs = qs[:opts["limit"]]

        self.stdout.write(self.style.NOTICE(f"대상: {qs.count()}권 처리 시작"))
        changed = 0
        failed = 0
        updated_objs = []

        for book in qs.iterator(chunk_size=100):
            try:
                new_cover = fetch_cover_big(book.isbn)
                if not new_cover:
                    failed += 1
                    self.stdout.write(f"[MISS] {book.isbn} cover 없음")
                else:
                    if book.cover_url != new_cover:
                        book.cover_url = new_cover
                        updated_objs.append(book)
                        changed += 1
                        self.stdout.write(f"[OK]   {book.isbn} → {new_cover}")
                    else:
                        self.stdout.write(f"[SKIP] {book.isbn} (이미 최신)")
            except Exception as e:
                failed += 1
                self.stderr.write(f"[ERR]  {book.isbn}: {e}")

            time.sleep(opts["sleep"])

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING(f"DRY-RUN: {changed}건 변경 예정, {failed}건 실패"))
            return

        if updated_objs:
            with transaction.atomic():
                BookInfo.objects.bulk_update(updated_objs, ["cover_url"], batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"완료: 변경 {changed}건, 실패 {failed}건"))
