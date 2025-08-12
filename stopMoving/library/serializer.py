from rest_framework import serializers
from .models import Library

class LibraryInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Library
        fields = ['id', 'name', 'address', 'contact', 'closed_days', 'hours_of_use', 'sns']