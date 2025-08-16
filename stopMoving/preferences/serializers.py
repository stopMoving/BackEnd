from rest_framework import serializers

class ISBNListSerializer(serializers.Serializer):
    isbns = serializers.ListField(
        child=serializers.RegexField(r'^\d{10,13}$'),  # 또는 CharField(min/max)
        min_length=5,
        max_length=5,
        allow_empty=False,
    )
