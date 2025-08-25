from datetime import timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Notification
from .serializers import NotificationSerializer
from django.db import transaction

class NotificationListView(APIView):
    """
    알림 목록 조회
    생성 후 30일 이내 모든 알림
    """
    permission_classes = [IsAuthenticated]
    def get(self, request):
        page = int(request.GET.get("page", 1))
        size = int(request.GET.get("size", 20))

        since = timezone.now() - timedelta(days=30)

        # 30이내 알림 최신순으로 정렬
        qs = (Notification.objects
              .filter(user=request.user, created_at__gte=since)
              .order_by("-created_at"))
        
        with transaction.atomic():  # ADDED: 대량 업데이트 원자성 보장
            (Notification.objects
             .filter(user=request.user, created_at__gte=since, is_read=False)  # CHANGED: 범위 제한
             .update(is_read=True, read_at=timezone.now()))
        
        total = qs.count()
        if total==0:
            return Response({
                "total": 0,
                "page": page,
                "size": size,
                "results": "받은 알림이 없습니다."
            }, status=status.HTTP_200_OK)
        items = qs[(page - 1) * size : page * size]

        data = NotificationSerializer(items, many=True).data

        return Response({
            "total": total,
            "page": page,
            "size": size,
            "results": data
        }, status=status.HTTP_200_OK)
    
class NotificationUnreadCountView(APIView):
    """
    알림 미읽음 개수 (30일 이내 범위)
    페이지 진입 전 헤더 뱃지/아이콘 등에 사용
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        since = timezone.now() - timedelta(days=30)
        unread = Notification.objects.filter(
            user=request.user,
            created_at__gte=since,
            is_read=False
        ).count()
        return Response({"unread": unread}, status=status.HTTP_200_OK)
