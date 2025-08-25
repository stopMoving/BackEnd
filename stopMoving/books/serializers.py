# books/serializers.py
from rest_framework import serializers
import re
    
class StockItemSerializer(serializers.Serializer):
    isbn = serializers.CharField()                   # 숫자로 와도 str로 캐스팅 가능
    quantity = serializers.IntegerField(min_value=1)

    def validate_isbn(self, v):
        # 숫자로 들어오면 문자열로 변환
        v = str(v).replace("-", "").strip()
        # if not re.fullmatch(r"\d{10}|\d{13}", v):
        #     raise serializers.ValidationError("ISBN은 10자리 또는 13자리여야 합니다.")
        return v

class StockBatchRequestSerializer(serializers.Serializer):
    library_id = serializers.IntegerField()
    books = StockItemSerializer(many=True)

