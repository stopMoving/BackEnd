from rest_framework import serializers
import re

# Donate 단권, 여러권 모두 허용
class DonationItemSerializer(serializers.Serializer):
    isbn = serializers.CharField()
    title = serializers.CharField(required=False, allow_blank=True)
    author = serializers.CharField(required=False, allow_blank=True)
    publisher = serializers.CharField(required=False, allow_blank=True)
    regular_price = serializers.IntegerField(required=False, min_value=0)

    def validate_isbn(self, v):
        v2 = v.replace("-", "").strip()
        if not re.fullmatch(r"\d{10}|\d{13}", v2):
            raise serializers.ValidationError("ISBN은 10자리 또는 13자리여야 합니다.")
        return v2

class DonationSerializer(serializers.Serializer):
    library_id = serializers.IntegerField()
    items = DonationItemSerializer(many=True)

    # 단권 바디도 허용 → 자동으로 items로 감싸기
    def to_internal_value(self, data):
        if "items" not in data and "isbn" in data:
            data = {
                "library_id": data.get("library_id"),
                "items": [{
                    "isbn": data.get("isbn"),
                    "title": data.get("title", ""),
                    "author": data.get("author", ""),
                    "publisher": data.get("publisher", ""),
                    "regular_price": data.get("regular_price"),
                }]
            }
        return super().to_internal_value(data)

    def validate(self, data):
        if not data["items"]:
            raise serializers.ValidationError("기증할 도서가 1권 이상이어야 합니다.")
        return data

# Pickup 단권, 여러권 모두 허용
class PickupItemSerializer(serializers.Serializer):
    isbn = serializers.CharField()
    regular_price = serializers.IntegerField(required=False, min_value=0)

    def validate_isbn(self, v):
        v2 = v.replace("-", "").strip()
        if not re.fullmatch(r"\d{10}|\d{13}", v2):
            raise serializers.ValidationError("ISBN은 10자리 또는 13자리여야 합니다.")
        return v2

class PickupSerializer(serializers.Serializer):
    library_id = serializers.IntegerField()
    items = PickupItemSerializer(many=True)

    def to_internal_value(self, data):
        if "items" not in data and "isbn" in data:
            data = {
                "library_id": data.get("library_id"),
                "items": [{
                    "isbn": data.get("isbn"),
                    "regular_price": data.get("regular_price"),
                }]
            }
        return super().to_internal_value(data)

    def validate(self, data):
        if not data["items"]:
            raise serializers.ValidationError("가져갈 도서가 1권 이상이어야 합니다.")
        return data
