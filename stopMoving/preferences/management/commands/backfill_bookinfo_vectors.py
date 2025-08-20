# preferences/management/commands/backfill_bookinfo_vectors.py
from django.core.management.base import BaseCommand
from bookinfo.models import BookInfo
from preferences.services.embeddings import load_vectorizer, build_text_from_bookinfo, serialize_sparse

class Command(BaseCommand):
    help = "기존 BookInfo.vector 백필"

    def handle(self, *args, **opts):
        vec = load_vectorizer()
        qs = BookInfo.objects.all()
        for bi in qs.iterator(chunk_size=500):
            if bi.vector:
                continue
            text = build_text_from_bookinfo(bi)
            X = vec.transform([text])
            bi.vector = serialize_sparse(X)
            bi.save(update_fields=["vector"])
        self.stdout.write(self.style.SUCCESS("backfill_bookinfo_vectors: done"))