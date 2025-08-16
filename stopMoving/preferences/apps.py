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
            pass
