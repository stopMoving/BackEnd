# preferences/apps.py
from django.apps import AppConfig

class PreferencesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'preferences'

    def ready(self):
        import os, sys
        if any(cmd in sys.argv for cmd in ['migrate','makemigrations','showmigrations','collectstatic','check','dbshell']):
            return
        if os.environ.get('DISABLE_PREFERENCES_PRELOAD') == '1':
            return
        try:
            from .services.keyword_extractor import preload
            preload()
        except Exception:
            pass
