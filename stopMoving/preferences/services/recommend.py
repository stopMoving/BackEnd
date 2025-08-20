# preferences/services/recommend.py
from typing import List, Tuple
import numpy as np
from scipy import sparse

def cosine_topk(user_csr, items, k=5):
    if user_csr is None:
        return []
    # ✅ (isbn, csr) 2-튜플만 깨끗하게 사용
    cleaned = []
    for t in items:
        if not (isinstance(t, (tuple, list)) and len(t) == 2):
            continue
        isbn, csr = t
        # csr 처럼 보이는지 최종 확인
        if csr is None or not hasattr(csr, "shape"):
            continue
        cleaned.append((isbn, csr))
    if not cleaned:
        return []

    mats = sparse.vstack([v for _, v in cleaned])
    # TF-IDF는 norm=l2라 dot = cosine
    scores = (mats @ user_csr.T).toarray().ravel()
    if scores.size == 0:
        return []

    idx = np.argsort(-scores)[:k]
    out = []
    for i in idx:
        try:
            out.append((cleaned[i][0], float(scores[i])))
        except Exception:
            # 인덱싱 오류 등 방어
            continue
    return out
