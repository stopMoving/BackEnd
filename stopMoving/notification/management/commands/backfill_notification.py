import re
from django.core.management.base import BaseCommand
from django.db import transaction
from notification.models import Notification
from books.models import Book

TOKEN = re.compile(r"#B(\d+)")

def build_msg_donated(title: str) -> str:
    return f"<<{title}>> 을 나눔했어요!\n+500P 적립"

def build_msg_pickup(title: str) -> str:
    return f"<<{title}>> 을 데려왔어요!\n좋은 시간 보내세요"

class Command(BaseCommand):
    help = "Rewrite existing notification messages to new format using #B<book_id> token."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show changes only")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        qs = Notification.objects.filter(message__regex=r"#B\d+")
        changed = 0

        with transaction.atomic():
            for n in qs.iterator():
                m = TOKEN.search(n.message or "")
                if not m:
                    continue
                book_id = int(m.group(1))
                b = (Book.objects
                        .select_related("isbn")
                        .only("id", "isbn__title")
                        .filter(id=book_id).first())
                if not b:
                    continue
                title = getattr(b.isbn, "title", None) or "도서"

                if n.type == "book_donated":
                    new_msg = build_msg_donated(title)
                elif n.type == "book_pickup":
                    new_msg = build_msg_pickup(title)
                else:
                    continue

                if n.message.strip() == new_msg.strip():
                    continue

                if dry:
                    self.stdout.write(f"[DRY] #{n.id}: '{n.message[:40]}...' -> '{new_msg}'")
                else:
                    n.message = new_msg
                    n.save(update_fields=["message"])
                    changed += 1

        if dry:
            self.stdout.write(self.style.WARNING("Dry run complete. No rows updated."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Rewrote {changed} notifications."))
