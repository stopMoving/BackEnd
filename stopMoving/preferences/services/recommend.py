# preferences/services/recommend.py
from typing import List
import numpy as np
from scipy import sparse

def _clean_items(items):
    cleaned = []
    for t in items:
        if not (isinstance(t, (tuple, list)) and len(t) == 2):
            continue
        isbn, csr = t
        if csr is None or not hasattr(csr, "shape") or getattr(csr, "nnz", 0) == 0:
            continue
        cleaned.append((isbn, csr))
    return cleaned

def cosine_topk(user_csr, items, k=5):
    if user_csr is None:
        return []
    cleaned = _clean_items(items)
    if not cleaned: return []
    M = sparse.vstack([v for _, v in cleaned])
    scores = (M @ user_csr.T).toarray().ravel()
    idx = np.argsort(-scores)[:k]
    return [(cleaned[i][0], float(scores[i])) for i in idx]

# (cleaned_items, M, base_scores) 반환
def cosine_scores(user_csr, items):
    cleaned = _clean_items(items)
    if not cleaned:
        return [], None, np.array([])
    M = sparse.vstack([v for _, v in cleaned])
    scores = (M @ user_csr.T).toarray().ravel()
    return cleaned, M, scores

# combined/activity 모드에 따라 추가 점수 부여
def apply_boosts(mode: str,
                 M: sparse.csr_matrix,
                 base_scores: np.ndarray,
                 survey_vec: sparse.csr_matrix | None,
                 recent_vec: sparse.csr_matrix | None,
                 survey_w: float = 0.25,
                 recent_w: float = 0.30) -> np.ndarray:
    scores = base_scores.copy()
    if mode == "combined" and survey_vec is not None and getattr(survey_vec, "nnz", 0) > 0:
        scores += survey_w * (M @ survey_vec.T).toarray().ravel()
    if mode == "activity" and recent_vec is not None and getattr(recent_vec, "nnz", 0) > 0:
        scores += recent_w * (M @ recent_vec.T).toarray().ravel()
    return scores

def mmr_rerank(M: sparse.csr_matrix,
               scores: np.ndarray,
               k: int = 5,
               pool: int = 100,
               lam: float = 0.3) -> List[int]:
    if M is None or M.shape[0] == 0:
        return []
    # 후보: base score 상위인 pool개
    top_idx = np.argsort(-scores)[:min(pool, M.shape[0])]
    M_pool = M[top_idx] # (P, D)
    rel = scores[top_idx] # (P, )

    selected = []
    cand_mask = np.ones(M_pool.shape[0], dtype=bool)

    for _ in range(min(k, M_pool.shape[0])):
        if not selected:
            i = int(np.argmax(rel))
            selected.append(i)
            cand_mask[i] = False
            continue
        # 현재 선택된 것과의 유사도 중 최대값 계싼
        M_sel = M_pool[selected] # (s, D)
        # (P, D) @ (D, s) -> (P, s) -> 각 후보별 최대 유사도
        sims = (M_pool @ M_sel.T).toarray()
        max_sim = sims.max(axis=1) # (P, )
        mmr = lam * rel - (1 - lam) * max_sim
        mmr[~cand_mask] = -1e9 # 이미 뽑힌 후보는 제외
        i = int(np.argmax(mmr))
        if not cand_mask[i]:
            break
        selected.append(i)
        cand_mask[i] = False

    # pool 내 인덱스를 원본 인덱스로 환산
    return [int(top_idx[i]) for i in selected]