from rest_framework import serializers
from .models import Library
from bookinfo.models import BookInfo
from books.models import Book

class LibraryInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Library
        fields = ['id', 'name', 'address', 'contact', 'closed_days', 'hours_of_use', 'sns', 'lat', 'long']

class LibraryHoldingItemSerializer(serializers.ModelSerializer):
    isbn = serializers.CharField(source="isbn.isbn")
    title = serializers.CharField(source="isbn.title")
    author = serializers.CharField(source="isbn.author")
    publisher = serializers.CharField(source="isbn.publisher")
    cover = serializers.URLField(source="isbn.cover_url", allow_blank=True, required=False)

    class Meta:
        model = Book
        fields = ["isbn", "title", "author", "publisher", "cover"]
        extra_kwargs = {
            "cover": {"help_text": "표지 이미지 URL"}
        }

class LibraryNameSerializer(serializers.ModelSerializer):
    class Meta:
        model=Library
        fields = ("id", "name")