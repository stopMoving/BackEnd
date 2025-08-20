# preferences/management/commands/fit_vectorizer.py
from django.core.management.base import BaseCommand
from bookinfo.models import BookInfo
from preferences.services.embeddings import ensure_vectorizer, build_text_from_bookinfo

class Command(BaseCommand):
    help = "TF-IDF 벡터라이저 학습(vectorizer.pkl 생성)"

    def handle(self, *args, **opts):
        qs = BookInfo.objects.all()
        corpus = [build_text_from_bookinfo(bi) for bi in qs]
        ensure_vectorizer(corpus)
        self.stdout.write(self.style.SUCCESS(f"fit_vectorizer: trained on {len(corpus)} docs"))