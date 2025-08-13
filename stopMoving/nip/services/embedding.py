# 임베딩 유틸: 멀티링구얼 SBERT 모델 1회 로딩 + 평균 벡터 계산
from sentence_transformers import SentenceTransformer
import numpy as np

_model = None

def get_model():
    global _model
    if _model is None:
        # 한국어/영어에 안정적인 384차원 모델
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model

# 단일 텍스트를 L2 정규화 임베딩(list[float])로 변환
def embed_text(text: str):
    model = get_model()
    vec = model.encode([text or ""], normalize_embeddings=True)[0]
    return vec.tolist()

# 여러 텍스트를 임베딩(Numpy array)으로 변환
def embed_texts(texts):
    model = get_model()
    arr = model.encode([t or "" for t in texts], normalize_embeddings=True)
    return arr  # numpy array

# 벡터(리스트 또는 np.array)의 평균(리스트)
def average_vectors(vectors):
    if isinstance(vectors, list):
        arr = np.array(vectors)
    else:
        arr = vectors
    return (arr.mean(axis=0)).tolist()
