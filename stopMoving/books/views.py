from django.shortcuts import render
# books/views.py
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import Book
from .serializers import BookPickRequestSerializer

class PickBooksAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        장바구니 book_ids를 받아서
        - 만료되지 않았고(expire_date >= now)
        - 현재 AVAILABLE 인 책만
        """
        s = BookPickRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        book_ids = s.validated_data["book_ids"]

        # 현재 시각
        now = timezone.now()

        # 기본 결과 틀
        results = {bid: {"updated": False, "reason": None} for bid in book_ids}

        # DB에서 정보 가져오기
        existing_qs = Book.objects.filter(id__in=book_ids).only("id", "status", "expire_date")
        existing_by_id = {b.id: b for b in existing_qs}

        with transaction.atomic():
            # 잠금 + 조건 충족분만 선별
            lock_qs = (
                Book.objects
                .select_for_update(skip_locked=True)
                .filter(id__in=book_ids, status="AVAILABLE")
                .exclude(expire_date__lt=now)
            )

            # 이번 호출에서 실제로 갱신될 id 집합
            will_update_ids = list(lock_qs.values_list("id", flat=True))

            # 일괄 상태 변경
            if will_update_ids:
                (Book.objects
                     .filter(id__in=will_update_ids)
                     .update(status="PICKED"))

        # id별 결과/사유 채우기
        for bid in book_ids:
            b = existing_by_id.get(bid)
            # 존재하지 않으면
            if not b:
                results[bid] = {"updated": False, "reason": "NOT_FOUND"}
                continue
            # 존재할 때
            if bid in will_update_ids:
                results[bid] = {"updated": True, "reason": None}
                continue

            # 실패 사유 상세
            if b.expire_date and b.expire_date < now:
                results[bid] = {"updated": False, "reason": "EXPIRED"}
            elif b.status != "AVAILABLE":
                results[bid] = {"updated": False, "reason": f"ALREADY_{b.status}"}
            else:
                # 동시성 등으로 조건 미충족
                results[bid] = {"updated": False, "reason": "CONFLICT"}

        updated_count = sum(1 for v in results.values() if v["updated"])
        return Response(
            {"updated_count": updated_count, "results": results},
            status=status.HTTP_200_OK
        )
