from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

# ⬇️ 네 프로젝트 경로에 맞게! (bookinfo.models 가 맞는지 확인)
from bookinfo.models import BookInfo, BookInfoLibrary, Library

class Command(BaseCommand):
    help = "Distribute BookInfo evenly across N libraries by updating BookInfoLibrary.quantity."

    def add_arguments(self, parser):
        parser.add_argument("--library-ids", nargs="+", type=int, help="Target library IDs; default first 10.")
        parser.add_argument("--qty-per-isbn", type=int, default=1, help="How many to add per ISBN (default 1).")
        parser.add_argument("--limit", type=int, default=None, help="Limit number of ISBNs.")
        parser.add_argument("--dry-run", action="store_true", help="Print plan only.")

    def handle(self, *args, **opts):
        lib_ids = opts.get("library_ids")
        qty = opts.get("qty_per_isbn", 1)
        limit = opts.get("limit")
        dry = opts.get("dry_run", False)

        # 1) 대상 도서관
        if lib_ids:
            libraries = list(Library.objects.filter(id__in=lib_ids).order_by("id"))
        else:
            libraries = list(Library.objects.order_by("id")[:10])
        if not libraries:
            raise CommandError("No target libraries.")
        L = len(libraries)

        # 2) 대상 ISBN
        qs = BookInfo.objects.order_by("isbn")
        if limit:
            qs = qs[:limit]

        created, updated = 0, 0
        now = timezone.now()

        # 3) 분배
        with transaction.atomic():
            for idx, info in enumerate(qs):
                target_lib = libraries[idx % L]
                bil, was_created = BookInfoLibrary.objects.get_or_create(
                    # ⚠️ 필드명이 library인지 library_id인지 정확히 맞춰!
                    library_id=target_lib,   # 만약 모델이 library(FK)면: library=target_lib
                    isbn=info,
                    defaults={"quantity": 0, "status": "AVAILABLE"},
                )
                if not dry:
                    bil.quantity += qty
                    bil.save(update_fields=["quantity"])
                created += int(was_created)
                updated += 1

        msg = f"Done. rows_created={created}, rows_updated={updated}, libraries={L}, qty_per_isbn={qty}"
        if dry:
            msg = "[DRY RUN] " + msg
        self.stdout.write(self.style.SUCCESS(msg))
