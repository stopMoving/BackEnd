# preferences/services/keyword_extractor.py

from __future__ import annotations
import re
from typing import List

# ====== 모델 로딩 (한 번만) ======
from sentence_transformers import SentenceTransformer
from keybert import KeyBERT

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model = None
_kw = None


def _get_kw() -> KeyBERT:
    """KeyBERT 인스턴스를 1회만 생성해서 재사용 (lazy singleton)."""
    global _kw, _model
    if _kw is None:
        if _model is None:
            # 최초 1회만 다운로드/로드. 이후 캐시 재사용.
            _model = SentenceTransformer(MODEL_NAME)
        _kw = KeyBERT(model=_model)
    return _kw


def preload() -> None:
    """
    서버 시작 시 미리 호출하면 최초 요청 지연을 줄일 수 있음.
    예) preferences/apps.py 의 ready()에서 preload() 한번 호출
    """
    _ = _get_kw()


# ====== 한국어 전처리 ======
# 최소 불용어(조사/접속사 등). 필요 시 자유롭게 추가하세요.
KOREAN_STOPWORDS = {
    "은", "는", "이", "가", "을", "를", "에", "에서",
    "와", "과", "으로", "으로서", "으로써", "에게", "께", "한테",
    "보다", "처럼", "부터", "까지", "도", "만", "조차", "마저",
    "의", "및", "또는", "그리고", "하지만", "그러나", "또", "혹은",
    "등", "등등", "요", "게", "데", "고", "라", "다", "것", "수", "들",
}

# 간단한 기호/영문/숫자 제거용
_PUNCT_NUM_ASCII = re.compile(r"[^\uac00-\ud7a3\s]")  # 한글 범위 이외 제거(간단화)


def _normalize_text_ko(text: str) -> str:
    # 줄바꿈을 공백으로, 과도한 공백 정리
    text = text.replace("\r", " ").replace("\n", " ")
    text = _PUNCT_NUM_ASCII.sub(" ", text)  # 숫자/기호/영문 제거(필요시 조정)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# 형태소 분석기: Kiwi → Okt → 토큰화 폴백
_use_kiwi = None
_use_okt = None
_kiwi = None
_okt = None

def _ensure_tokenizer():
    global _use_kiwi, _use_okt, _kiwi, _okt
    if _use_kiwi is not None or _use_okt is not None:
        return
    try:
        # pip install kiwipiepy
        from kiwipiepy import Kiwi  # type: ignore
        _kiwi = Kiwi()
        _use_kiwi = True
        _use_okt = False
        return
    except Exception:
        pass
    try:
        # pip install konlpy JPype1 (Windows는 설치가 까다로울 수 있습니다)
        from konlpy.tag import Okt  # type: ignore
        _okt = Okt()
        _use_okt = True
        _use_kiwi = False
        return
    except Exception:
        _use_kiwi = False
        _use_okt = False


def _tokenize_keep_nv(text: str) -> List[str]:
    """
    한국어 텍스트에서 명사/동사만 남겨 토큰 리스트로 반환.
    형태소 분석기가 없으면 간단 분절 + 불용어 제거로 폴백.
    """
    _ensure_tokenizer()
    text = _normalize_text_ko(text)

    # 1) Kiwi: 품사 태그가 'N', 'V'로 시작하는 것만 채택
    if _use_kiwi:
        tokens = []
        for token in _kiwi.tokenize(text, normalize_coda=True):
            pos = token.tag  # 예: NNG, NNP, VV 등
            if pos.startswith("N") or pos.startswith("V"):
                lemma = token.form  # 원형
                if lemma and lemma not in KOREAN_STOPWORDS and len(lemma) > 1:
                    tokens.append(lemma)
        return tokens

    # 2) Okt: Noun/Verb만, 동사는 어간 추출(stem=True)
    if _use_okt:
        tokens = []
        for word, pos in _okt.pos(text, norm=True, stem=True):
            if pos in ("Noun", "Verb"):
                if word and word not in KOREAN_STOPWORDS and len(word) > 1:
                    tokens.append(word)
        return tokens

    # 3) 폴백: 공백 분절 + 불용어 제거 + 2글자 이상만
    rough = [w for w in text.split() if len(w) > 1]
    return [w for w in rough if w not in KOREAN_STOPWORDS]

# preferences/services/keyword_extractor.py (핵심 부분만)
import json, os, re, math
from typing import List, Dict, Tuple
from collections import Counter, defaultdict

# ... (기존: _get_kw, _normalize_text_ko, _tokenize_keep_nv 유지)
IDF_PATH = os.path.join(os.path.dirname(__file__), "idf.json")
_IDF: Dict[str, float] | None = None

def _load_idf() -> Dict[str, float]:
    global _IDF
    if _IDF is None:
        try:
            with open(IDF_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                _IDF = data.get("idf", {})
        except Exception:
            _IDF = {}
    return _IDF

def _keybert_uniwords(text: str, top_k: int = 15) -> List[Tuple[str, float]]:
    """한 단어만 후보로 뽑되, 전처리된 텍스트를 사용."""
    kw = _get_kw()
    pairs = kw.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 1),
        stop_words=None,      # 이미 전처리에서 정리
        top_n=top_k,
        use_mmr=True,
        diversity=0.6,
        nr_candidates=20
    )
    # [(word, score)] 그대로 반환
    return pairs

def extract_keywords_from_books(records: List[Dict], top_n: int = 4) -> List[str]:
    """
    3권 레코드 [{title, author, category, description}, ...]를 받아
    1-gram 키워드를 사전 없이 일반적으로 추출.
    """
    if not records:
        return []

    # 1) 각 책별 전처리 & 단어 리스트
    book_tokens: List[List[str]] = []
    processed_texts: List[str] = []
    for d in records:
        parts = [d.get("title") or "", d.get("author") or "", d.get("category") or "", d.get("description") or ""]
        raw = " \n".join([p.strip() for p in parts if p and p.strip()])
        toks = _tokenize_keep_nv(raw)
        if not toks:
            toks = []
        book_tokens.append(toks)
        processed_texts.append(" ".join(toks))

    # 2) 각 책별 KeyBERT 단어 점수
    kb_scores_per_book: List[Dict[str, float]] = []
    for text in processed_texts:
        pairs = _keybert_uniwords(text, top_k=max(top_n * 3, 15))
        kb_scores_per_book.append({w.strip(): s for w, s in pairs if w and len(w.strip()) > 1})

    # 3) 교집합(등장 문서 수) 가중치
    doc_freq = Counter()
    for d in kb_scores_per_book:
        doc_freq.update(set(d.keys()))  # 문서 내 중복 제거

    # 4) 전역 IDF 로드 (없으면 1.0으로 처리)
    idf = _load_idf()

    # 5) 최종 점수 = 평균 KeyBERT 점수 × (1 + α·IDF) × (1 + β·DocFreqBoost)
    #    - α: IDF 중요도 (0.5~1.0), β: 교집합 보너스 (예: 0.3)
    α, β = 0.7, 0.3
    agg = defaultdict(list)
    for d in kb_scores_per_book:
        for w, s in d.items():
            agg[w].append(s)

    scored: List[Tuple[str, float]] = []
    for w, arr in agg.items():
        avg_s = sum(arr) / len(arr)
        idf_w = idf.get(w, 1.0)  # 없으면 1.0
        df_boost = (doc_freq[w] - 1)  # 3권 중 2권에 나오면 1, 3권이면 2
        final = avg_s * (1.0 + α * idf_w) * (1.0 + β * max(0, df_boost))
        # 영문/숫자/한글만 허용 (기호 제거), 너무 짧은 토큰 제외
        if not re.fullmatch(r"[0-9A-Za-z\uac00-\ud7a3]{2,}", w):
            continue
        scored.append((w, final))

    # 6) 정렬 + 상위 top_n
    scored.sort(key=lambda x: x[1], reverse=True)
    out, seen = [], set()
    for w, _ in scored:
        if w.lower() in seen:
            continue
        seen.add(w.lower())
        out.append(w)
        if len(out) >= top_n:
            break
    return out
