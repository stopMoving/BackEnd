# bookinfo/serializers.py
import re
from rest_framework import serializers
from .models import BookInfo
from books.serializers import IsbnListField

# (공통 베이스) 응답 기본 스키마
class BookInfoPublicBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookInfo
        fields = (
            "isbn", "title", "author", "publisher",
            "published_date", "cover_url", "category",
            "regular_price", "description",
        )

# (저장용) 알라딘 등에서 받은 값 저장/갱신
class BookInfoUpsertSerializer(serializers.ModelSerializer):
    published_date = serializers.DateField(
        required=False, allow_null=True,
        input_formats=["%Y-%m-%d", "%Y%m%d", "%Y.%m.%d"],
    )

    class Meta:
        model = BookInfo
        # 내부용 vector는 받지 않음
        fields = (
            "isbn", "title", "author", "publisher",
            "published_date", "cover_url", "category",
            "regular_price", "description",
        )
        extra_kwargs = {
            "title": {"allow_blank": True},
            "author": {"allow_blank": True},
            "publisher": {"allow_blank": True},
            "category": {"allow_blank": True},
            "description": {"allow_blank": True},
        }

    def validate_isbn(self, v):
        v = v.replace("-", "").strip()
        if not re.fullmatch(r"\d{10}|\d{13}", v):
            raise serializers.ValidationError("ISBN은 10자리 또는 13자리여야 합니다.")
        return v

# (나눔 화면 전용) 필요한 필드만
class DonationDisplaySerializer(BookInfoPublicBaseSerializer):
    class Meta(BookInfoPublicBaseSerializer.Meta):
        fields = ("isbn", "title", "author", "publisher")

# (픽업 화면 전용) 정가 + 85% 할인 판매가 포함
from decimal import Decimal, ROUND_FLOOR
DISCOUNT_RATE = Decimal("0.15")

class PickupDisplaySerializer(BookInfoPublicBaseSerializer):
    sale_price = serializers.SerializerMethodField()

    class Meta(BookInfoPublicBaseSerializer.Meta):
        # 요구사항: 제목, 저자, 출판사, 정가, 판매가, isbn
        fields = ("isbn", "title", "author", "publisher", "regular_price", "sale_price", "cover_url")

    def get_sale_price(self, obj):
        # 정가 없으면 판매가는 고정 2000원
        if obj.regular_price is None:
            return 2000
        # 정가 있으면 85% 내림
        return int((Decimal(obj.regular_price) * DISCOUNT_RATE).to_integral_value(rounding=ROUND_FLOOR))
    
class BookDetailDisplaySerializer(BookInfoPublicBaseSerializer):
    sale_price = serializers.SerializerMethodField()

    class Meta(BookInfoPublicBaseSerializer.Meta):
        # 요구사항: 제목, 저자, 출판사, 정가, 판매가, isbn
        fields = ("isbn", "title", "author", "publisher", "regular_price", "sale_price", "cover_url","description")

    def get_sale_price(self, obj):
        # 정가 없으면 판매가는 고정 2000원
        if obj.regular_price is None:
            return 2000
        # 정가 있으면 85% 내림
        return int((Decimal(obj.regular_price) * DISCOUNT_RATE).to_integral_value(rounding=ROUND_FLOOR))
    
class BookInfoSerializer(serializers.Serializer):
    isbn = IsbnListField()  # 단/복수 모두 여기로
