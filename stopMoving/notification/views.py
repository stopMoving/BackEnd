from datetime import timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Notification
from .serializers import NotificationSerializer


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

        total = qs.count()
        items = qs[(page - 1) * size : page * size]

        return Response({
            "total": total,
            "page": page,
            "size": size,
            "results": NotificationSerializer(items, many=True).data
        }, status=status.HTTP_200_OK)
