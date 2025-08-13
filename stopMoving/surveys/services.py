# 설문 처리 서비스: DB 읽고 NLP 수행하고 UserInfo/SurveyResponse 갱신
from django.utils import timezone
from bookinfo.models import BookInfo
from users.models import UserInfo
from nip.services.keyword_extractor import extract_keywords
from nip.services.embedding import embed_texts, average_vectors
from .models import SurveyResponse

# 키워드 추출용 텍스트 결합
def _join_book_fields(b: BookInfo) -> str:
    parts = [b.title, b.author, b.publisher, b.category, b.description]
    return " ".join([p for p in parts if p])

# 설문 처리: ISBN 3개 → 키워드/벡터 생성 → 저장 후 결과 반환
def run_survey_and_save(user, isbns, top_k=5):
    books = list(BookInfo.objects.filter(pk__in=isbns)[:3])

    # 텍스트 결합
    corpus = "\n".join([_join_book_fields(b) for b in books])

    # 1) 키워드 추출
    keywords = extract_keywords(corpus, top_k=top_k)

    # 2) 사용자 벡터 = 키워드 임베딩 평균 (없으면 설명 임베딩 평균 fallback)
    if keywords:
        kw_vecs = embed_texts(keywords)      # np.array
        user_vec = average_vectors(kw_vecs)  # list[float]
    else:
        descs = [(b.description or b.title) for b in books]
        user_vec = average_vectors(embed_texts(descs))

    # 3) 설문 기록 저장
    SurveyResponse.objects.create(
        user=user,
        selected_isbns=[b.pk for b in books],
        extracted_keywords=keywords,
        generated_vector=user_vec,
    )

    # 4) UserInfo 갱신
    profile, _ = UserInfo.objects.get_or_create(user=user)
    profile.preference_keyword = keywords
    profile.preference_vector = user_vec
    profile.survey_done = True
    profile.last_survey_at = timezone.now()
    profile.save()

    return keywords, user_vec
