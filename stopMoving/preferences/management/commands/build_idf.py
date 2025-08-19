# preferences/management/commands/build_idf.py
# TF: 문서 내 단어 빈도
# IDF: 전체 문서에서 단어 빈도
# 제목+저자+카테고리+설명 -> 키워드별 IDF 생성
from django.core.management.base import BaseCommand
from bookinfo.models import BookInfo
import json, math
from collections import Counter

from preferences.services.keyword_extractor import _tokenize_keep_nouns, _normalize_text_ko

class Command(BaseCommand):
    help = "Build global IDF from BookInfo corpus"

    def add_arguments(self, parser):
        parser.add_argument("--out", default="idf.json")

    def handle(self, *args, **opts):
        N = 0
        df = Counter()
        qs = BookInfo.objects.values_list("category", "description")
        for category, desc in qs.iterator(chunk_size=1000):
            text = " ".join(filter(None, [category or "", desc or ""]))
            text = _normalize_text_ko(text)
            toks = set(_tokenize_keep_nouns(text))  # 문서 내 중복 제거
            if not toks:
                continue
            for t in toks:
                df[t] += 1
            N += 1

        idf = {t: math.log((N + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        with open(opts["out"], "w", encoding="utf-8") as f:
            json.dump({"N": N, "idf": idf}, f, ensure_ascii=False)
        self.stdout.write(self.style.SUCCESS(f"Built IDF for {N} docs → {opts['out']}"))
