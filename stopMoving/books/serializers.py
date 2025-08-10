# books/serializers.py
from rest_framework import serializers

class BookPickRequestSerializer(serializers.Serializer):
    book_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False
    )
