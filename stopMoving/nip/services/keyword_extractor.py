# 키워드 추출: KeyBERT가 sentence-transformers 인스턴스를 재사용하도록 수정
from keybert import KeyBERT
import re
from nip.services.embedding import get_model  # ← 같은 모델을 공유

_kw = None

def _get_kw():
    global _kw
    if _kw is None:
        # 기존: KeyBERT(model="paraphrase-multilingual-MiniLM-L12-v2")
        # 변경: 이미 로딩된 sentence-transformers 인스턴스를 주입
        _kw = KeyBERT(model=get_model())
    return _kw

def _clean_list(cands, top_k=5):
    out, seen = [], set()
    for c in cands:
        s = re.sub(r"\s+", " ", (c or "").strip())
        s = s.strip(".,;:!?'\"()[]{}")
        if not s or len(s) < 2:
            continue
        low = s.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(s)
        if len(out) == top_k:
            break
    return out

def extract_keywords(text: str, top_k=5):
    if not text or not text.strip():
        return []
    model = _get_kw()
    pairs = model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 3),
        stop_words=None,
        top_n=20,
        use_maxsum=True,
        nr_candidates=40,
    )
    ranked = [k for k, _ in pairs]
    return _clean_list(ranked, top_k=top_k)
