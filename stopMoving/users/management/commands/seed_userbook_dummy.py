# users/management/commands/link_userbook_from_existing.py
from typing import List, Tuple
from itertools import cycle

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from users.models import UserBook, Status
from books.models import Book
from library.models import Library


class Command(BaseCommand):
    help = (
        "이미 존재하는 Book/User를 바탕으로 UserBook을 결정론적으로 생성합니다.\n"
        "- DONATED: donor_user가 있는 책을 기증 관계로 연결\n"
        "- PURCHASED: status='PICKED' 책을 --purchaser-ids로 전달된 유저들에게 라운드로빈 배정"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--mode",
            type=str,
            choices=["donated", "purchased", "both"],
            default="both",
            help="생성 모드 선택 (기본 both)",
        )
        parser.add_argument(
            "--library-ids",
            type=str,
            default="",
            help="대상 도서관 id들(쉼표로 구분). 지정 없으면 전체",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="처리 최대 건수 제한(0이면 제한 없음). 모드별 각각 적용",
        )
        parser.add_argument(
            "--purchaser-ids",
            type=str,
            default="",
            help="PURCHASED용 배정 사용자 id 목록(쉼표 구분). 예: 2,3,5 "
                 "※ 미지정 시 PURCHASED 생성은 건너뜀(랜덤 배정 없음).",
        )

    # ---------- helpers ----------
    def _parse_id_list(self, s: str) -> List[int]:
        if not s:
            return []
        out = []
        for tok in s.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                out.append(int(tok))
            except ValueError:
                pass
        return out

    # ---------- handle ----------
    def handle(self, *args, **opts):
        mode = opts["mode"]
        lib_ids = self._parse_id_list(opts.get("library_ids", ""))
        limit = int(opts.get("limit") or 0)
        purchaser_ids = self._parse_id_list(opts.get("purchaser_ids", ""))

        # 라이브러리 범위
        if lib_ids:
            libraries = list(Library.objects.filter(id__in=lib_ids).values_list("id", flat=True))
        else:
            libraries = list(Library.objects.all().values_list("id", flat=True))

        if not libraries:
            self.stderr.write(self.style.ERROR("Library 데이터가 없습니다. 먼저 라이브러리를 생성하세요."))
            return

        # 공통 Book 베이스 쿼리
        base_qs = Book.objects.select_related("library", "isbn").filter(library_id__in=libraries)

        total_created = 0

        # =========================
        # DONATED
        # =========================
        if mode in ("donated", "both"):
            donated_qs = (
                base_qs.exclude(donor_user__isnull=True)
                .order_by("id")
                .values_list("id", "donor_user_id")
            )

            # 이미 존재하는 (user, book) 조합은 제외
            existing_pairs = set(
                UserBook.objects.filter(book_id__in=[bid for bid, _ in donated_qs])
                .values_list("user_id", "book_id")
            )

            to_create_donated: List[UserBook] = []
            processed = 0
            for book_id, donor_uid in donated_qs:
                if limit and processed >= limit:
                    break
                processed += 1
                # donor가 없을 일은 exclude로 걸렀으니 안전
                if (donor_uid, book_id) in existing_pairs:
                    continue
                to_create_donated.append(
                    UserBook(user_id=donor_uid, book_id=book_id, status=Status.DONATED)
                )
                existing_pairs.add((donor_uid, book_id))

            if to_create_donated:
                with transaction.atomic():
                    UserBook.objects.bulk_create(to_create_donated, batch_size=1000)
                total_created += len(to_create_donated)

            self.stdout.write(self.style.SUCCESS(
                f"DONATED 생성: {len(to_create_donated)}건"
            ))

        # =========================
        # PURCHASED
        # =========================
        if mode in ("purchased", "both"):
            if not purchaser_ids:
                self.stdout.write(self.style.WARNING(
                    "PURCHASED 생성을 위해서는 --purchaser-ids 가 필요합니다. (랜덤 배정 없음) → PURCHASED 건너뜀"
                ))
            else:
                # status='PICKED' 책만 대상으로 (운영 흐름과 동일)
                picked_qs = (
                    base_qs.filter(status="PICKED")
                    .order_by("id")
                    .values_list("id", "donor_user_id")
                )

                existing_pairs = set(
                    UserBook.objects.filter(book_id__in=[bid for bid, _ in picked_qs])
                    .values_list("user_id", "book_id")
                )

                # 라운드로빈(결정론적) 배정
                rr = cycle(purchaser_ids)

                to_create_purchased: List[UserBook] = []
                processed = 0
                for book_id, donor_uid in picked_qs:
                    if limit and processed >= limit:
                        break
                    processed += 1

                    # donor와 동일한 유저에게는 배정하지 않음 → 다음 사람으로 넘어감
                    # 또한 이미 (user, book) 존재하면 다음 사람으로 넘어감
                    attempts = 0
                    max_attempts = len(purchaser_ids)
                    chosen_uid = None
                    while attempts < max_attempts:
                        uid = next(rr)
                        attempts += 1
                        if donor_uid and uid == donor_uid:
                            continue
                        if (uid, book_id) in existing_pairs:
                            continue
                        chosen_uid = uid
                        break

                    if not chosen_uid:
                        # 모든 후보가 donor 또는 중복이면 스킵
                        continue

                    to_create_purchased.append(
                        UserBook(user_id=chosen_uid, book_id=book_id, status=Status.PURCHASED)
                    )
                    existing_pairs.add((chosen_uid, book_id))

                if to_create_purchased:
                    with transaction.atomic():
                        UserBook.objects.bulk_create(to_create_purchased, batch_size=1000)
                    total_created += len(to_create_purchased)

                self.stdout.write(self.style.SUCCESS(
                    f"PURCHASED 생성: {len(to_create_purchased)}건"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"완료: UserBook 총 생성 {total_created}건"
        ))
