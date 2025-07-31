# src/logging_config.py
# 로깅 설정

import os
from datetime import datetime

# 로그 파일이 저장될 디렉토리
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': { # 로그 형식 정의
        'verbose': { # 시간, 레벨, 이름, 메시지 포함
            'format': '[{asctime}] {levelname} {name} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'access_file': { # INFO 레벨 이상의 로그를 파일에 기록
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, f'access-{today}.log'),
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'error_file': { # WARNING 레벨 이상의 로그를 파일에 기록
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, f'error-{today}.log'),
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': { # WARNING 레벨 이상의 로그를 콘솔에 출력
            'level': 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['access_file', 'error_file', 'console'],
        'level': 'DEBUG',
    },
}
