# books/serializers.py
from rest_framework import serializers
import re

class IsbnListField(serializers.ListField):
    """
    입력이 '문자열'이면 [문자열]로, '문자열 리스트'면 그대로.
    하이픈/공백 제거, 10/13자리 검증 후 리스트로 반환.
    """
    def to_internal_value(self, data):
        if isinstance(data, str):
            values = [data]
        elif isinstance(data, list):
            values = data
        else:
            raise serializers.ValidationError("isbn은 문자열 또는 문자열 리스트여야 합니다.")

        # 항상 리스트로 정규화
        norm = []
        for v in values:
            v2 = re.sub(r"[-\s]", "", v or "")
            if not re.fullmatch(r"\d{10}|\d{13}", v2):
                raise serializers.ValidationError(f"잘못된 ISBN 형식: {v}")
            norm.append(v2)
        return norm
    
    def to_representation(self, value):
        # 필요하면 항상 리스트로 응답. (요청은 단/복수 모두 허용)
        return list(value)
    
class BookIdListField(serializers.Field):
    """
    입력이 '문자열'이면 [id]로, '정수 리스트'면 그대로.
    모두 정수로 캐스팅하여 리스트로 반환.
    """
    def to_internal_value(self, data):
        if isinstance(data, str):
            values = [data]
        elif isinstance(data, int):
            values = [data]
        elif isinstance(data, list):
            values = data
        else:
            raise serializers.ValidationError("book_id는 정수 또는 정수 리스트여야 합니다.")

        norm = []
        for v in values:
            try:
                iv = int(v)
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"잘못된 book_id 형식: {v}")
            if iv <= 0:
                raise serializers.ValidationError(f"book_id는 양의 정수여야 합니다: {v}")
            norm.append(iv)
        return norm

    def to_representation(self, value):
        return list(value)

class DonationSerializer(serializers.Serializer):
    library_id = serializers.IntegerField()
    isbn = IsbnListField()  # ← 단/복수 모두 여기로

class PickupSerializer(serializers.Serializer):
    book_id = BookIdListField()

