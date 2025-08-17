from rest_framework import serializers
from .models import UserInfo, UserBook
from library.models import Library
from books.models import Book

# 마이페이지에 표시할 사용자 정보
class UserProfileSerializer(serializers.Serializer):
    nickname = serializers.CharField()
    points = serializers.IntegerField()
    keywords = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True
    )

# 사용자별 나눔하기/데려가기 한 책 목록
class UserBookSerializer(serializers.ModelSerializer):
    # 상태: 기증/구매
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    
    # 책 정보
    userbook_id = serializers.IntegerField(source='book.id')
    book_title = serializers.CharField(source='book.isbn.title')
    cover = serializers.URLField(source='book.isbn.cover_url')
    # 도서관 정보
    library_id = serializers.IntegerField(source='book.library.id')
    library_name = serializers.CharField(source='book.library.name')

    class Meta:
        model = UserBook
        fields = (
            'userbook_id', 'book_title', 'cover',
            'status', 'created_at', 'library_id', 'library_name'
        )