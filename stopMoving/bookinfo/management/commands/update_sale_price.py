import time
from django.core.management.base import BaseCommand
from django.db import transaction
from bookinfo.models import BookInfo
from django.conf import settings
from decimal import Decimal, ROUND_FLOOR

# 판매가 = 정가 * 0.15로 수정(할인률 85%), 정가 없으면 2000
def _calc_sale_price(regular_price):
        DISCOUNT_RATE = Decimal("0.85")
        if regular_price is None:
            return 2000
        return int((Decimal(regular_price) * (1 - DISCOUNT_RATE)).to_integral_value(rounding=ROUND_FLOOR))

class Command(BaseCommand):
    help = "알라딘 API를 다시 호출해 BookInfo.sale_price를 정가의 15% 가격으로 일괄 업데이트"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="처리할 최대 레코드 수(테스트용)")
        parser.add_argument("--dry-run", action="store_true", help="DB에 저장하지 않고 어떤 변경이 일어날지만 출력")
        parser.add_argument("--sleep", type=float, default=0.2, help="요청 간 대기(초), API rate limit 회피용")

    def handle(self, *args, **opts):
        if not settings.API_KEY:
            self.stderr.write(self.style.ERROR("settings.API_KEY가 없습니다. settings.py 또는 환경변수를 확인하세요."))
            return

        qs = BookInfo.objects.all().only("isbn", "regular_price", "sale_price")
        
        if opts["limit"]:
            qs = qs[:opts["limit"]]

        self.stdout.write(self.style.NOTICE(f"대상: {qs.count()}권 처리 시작"))
        changed = 0
        failed = 0
        updated_objs = []

        for book in qs.iterator(chunk_size=100):
            try:
                new_sale_price = _calc_sale_price(book.regular_price)
                if book.sale_price != new_sale_price:
                    book.sale_price = new_sale_price
                    updated_objs.append(book)
                    changed += 1
            except Exception as e:
                failed += 1
                self.stderr.write(f"[ERR]  {book.isbn}: {e}")

            time.sleep(opts["sleep"])

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING(f"DRY-RUN: {changed}건 변경 예정, {failed}건 실패"))
            return

        if updated_objs:
            with transaction.atomic():
                BookInfo.objects.bulk_update(updated_objs, ["sale_price"], batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"완료: 변경 {changed}건, 실패 {failed}건"))
