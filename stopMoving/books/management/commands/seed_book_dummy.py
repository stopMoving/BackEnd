# books/management/commands/seed_book_dummy.py
# Books 테이블의 더미 데이터를 생성하는 커맨드
import random
from itertools import cycle, islice
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from bookinfo.models import BookInfo
from library.models import Library
from django.contrib.auth import get_user_model

from books.models import Book

class Command(BaseCommand):
    help = "Book 테이블에 더미데이터를 삽입합니다. (중간테이블: Library × BookInfo)"

    # python manage/run_with_tunnel.py 커맨드 실행 시 추가 옵션을 받을 수 있도록 함(인자 정의)
    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=100, help="생성 개수 (기본 100)")
        parser.add_argument("--status", type=str, default="half", choices=["half", "available", "picked"],
                            help="상태 분포: half(절반씩), available(전부), picked(전부)")
        parser.add_argument("--library-ids", type=str, help="지정 라이브러리 id들(쉼표로 구분). 없으면 전체에서 랜덤")
        parser.add_argument("--only-priced", action="store_true",
                            help="정가가 있는 BookInfo만 사용")
        
    def handle(self, *args, **opts):
        count = opts["count"]
        status_mode = opts["status"]
        only_priced = opts["only_priced"]

        # 도서관 후보 선택
        if opts.get("library_ids"): # 지정된 도서관 ID가 있으면 해당 라이브러리만 사용
            ids = [int(x) for x in opts["library_ids"].split(",") if x.strip()]
            libraries = list(Library.objects.filter(id__in=ids))
        else:   # 지정된 도서관이 없으면 전체 라이브러리에서 랜덤 선택
            libraries = list(Library.objects.all())

        if not libraries:   # 라이브러리가 없으면 에러 메시지 출력 후 종료
            self.stderr.write(self.style.ERROR("Library 데이터가 없습니다. 먼저 라이브러리를 생성하세요."))
            return

        # BookInfo 후보 선택
        bookinfo_qs = BookInfo.objects.all()
        if only_priced: # BookInfo에서 정가가 있는 항목만 필터링
            bookinfo_qs = bookinfo_qs.exclude(regular_price__isnull=True)
        bookinfos = list(bookinfo_qs)

        if not bookinfos:   # BookInfo가 없으면 에러 메시지 출력 후 종료
            self.stderr.write(self.style.ERROR("BookInfo 데이터가 없습니다. 먼저 BookInfo를 적재하세요."))
            return

        # donor_user 후보 
        # 1~7 사이의 유저 ID를 가진 유저들 중에서 랜덤으로 선택
        User = get_user_model()
        user_ids = list(User.objects.filter(id__in=range(1, 8)).values_list("id", flat=True))

        # status 분포 - available, picked가 절반씩 나오도록 설정
        if status_mode == "half":
            status_cycle = cycle(["AVAILABLE", "PICKED"])
        elif status_mode == "available":
            status_cycle = cycle(["AVAILABLE"])
        else:
            status_cycle = cycle(["PICKED"])

        # 객체 생성
        now = timezone.now()
        objs: list[Book] = []
        for i in range(count):
            lib = random.choice(libraries)
            bi = random.choice(bookinfos)

            # donation_date/expire_date를 명시적으로 세팅 (bulk_create는 save()를 호출하지 않음)
            # 기증일: 현재 시각, 만료일: 기증일로부터 30일 후
            donation_date = now
            expire_date = donation_date + timedelta(days=30)

            obj = Book(
                library=lib,
                isbn_id=bi.isbn,                 # FK(to_field="isbn")이므로 _id에 문자열 ISBN 주입
                regular_price=bi.regular_price,  # BookInfo의 정가 복사
                donation_date=donation_date,
                expire_date=expire_date,
                status=next(status_cycle),
                donor_user_id=random.choice(user_ids),  # 1~7 사이 랜덤 유저 FK로 할당
            )
            objs.append(obj)

        # 대량 삽입
        with transaction.atomic():
            Book.objects.bulk_create(objs, batch_size=500)

        self.stdout.write(self.style.SUCCESS(f"완료: Book 더미 {len(objs)}건 생성"))