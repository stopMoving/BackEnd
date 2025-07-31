# config/middleware.py
# 로깅 요청을 위한 미들웨어
import logging

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logger.info(f"[{request.method}] {request.get_full_path()}")
        response = self.get_response(request)
        return response
