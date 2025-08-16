# preferences/apps.py
from django.apps import AppConfig

class PreferencesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'preferences'

    def ready(self):
        try:
            from .services.keyword_extractor import preload
            preload()
        except Exception:
            # 초기 부팅시 모델 다운로드 실패해도 서버는 뜨게 두고,
            # 첫 요청 시 재시도하게 만들려면 그냥 무시해도 됨.
            pass
