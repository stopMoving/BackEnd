# preferences/services/embeddings.py
import os, re, pickle, numpy as np
from typing import List, Optional
from django.conf import settings
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

TOKEN_RE = re.compile(r"[A-Za-z가-힣0-9]{2,}")

def _load_stopwords() -> set[str]:
    p = os.path.join(settings.VECTOR_DATA_DIR, "stopwords_ko.txt")
    if not os.path.exists(p):
        return set()
    with open(p, "r", encoding="utf-8") as f:
        return {w.strip() for w in f if w.strip() and not w.startswith("#")}
    
STOPWORDS = _load_stopwords()

def simple_tokenize(text: str) -> List[str]:
    if not text:
        return []
    toks = TOKEN_RE.findall(text.lower())
    return [t for t in toks if t not in STOPWORDS and len(t) > 1]

# bookinfo의 title, category, desc -> text 형태로 변환
def build_text_from_bookinfo(bi) -> str:
    title = (bi.title or "")[:80] # 한 줄만 받음
    return "".join(filter(None, [bi.category or "", bi.description or "", title]))

# meta용 빌더(기증 api에 활용)
def build_text_from_meta(meta: dict) -> str:
    title = (meta.get("title") or "")[:80]
    return "".join(filter(None, [
        meta.get("category") or "",
        meta.get("description") or "",
        title
    ]))

def ensure_vectorizer(corpus: Optional[List[str]] = None) -> TfidfVectorizer:
    os.makedirs(settings.VECTOR_DATA_DIR, exist_ok=True)
    path = settings.VECTOR_PICKLE_PATH
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    assert corpus is not None and len(corpus) > 0, "Vectorizer가 없어 corpus가 필요합니다."
    vec = TfidfVectorizer(
        tokenizer=simple_tokenize,
        ngram_range=(1,2),
        min_df=2, max_df=0.95,
        sublinear_tf=True, norm="l2"
    )
    vec.fit(corpus)
    with open(path, "wb") as f:
        pickle.dump(vec, f)
    return vec

def load_vectorizer() -> TfidfVectorizer:
    with open(settings.VECTOR_PICKLE_PATH, "rb") as f:
        return pickle.load(f)
    
def serialize_sparse(csr: sparse.csc_matrix) -> dict:
    csr = csr.tocsr()
    return {
        "data": csr.data.tolist(),
        "indices": csr.indices.tolist(),
        "indptr": csr.indptr.tolist(),
        "shape": csr.shape,
    }

def deserialize_sparse(obj: dict | None) -> Optional[sparse.csr_matrix]:
    if not obj:
        return None
    data = np.array(obj["data"]); ind = np.array(obj["indices"]); ptr = np.array(obj["indptr"])
    return sparse.csr_matrix((data, ind, ptr), shape=tuple(obj["shape"]))

def weighted_sum(v1: Optional[sparse.csr_matrix], v2: Optional[sparse.csr_matrix], alpha: float):
    if v1 is None: return v2
    if v2 is None: return v1
    return alpha * v1 + (1.0 - alpha) * v2

def l2_normalize(csr: sparse.csr_matrix | None):
    if csr is None or csr.nnz == 0:
        return csr
    csr = csr.tocsr(copy=True)
    n = float(np.sqrt((csr.data ** 2).sum()))
    if n > 0:
        csr.data /= n
    return csr