from rest_framework import serializers
from .models import UserInfo, UserBook, UserImage
from library.models import Library
from books.models import Book
from bookinfo.models import BookInfo

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
    bookinfo = serializers.IntegerField(source='bookinfo.isbn', read_only=True)
    title = serializers.CharField(source='bookinfo.title', read_only=True)
    cover = serializers.URLField(source='bookinfo.cover_url', read_only=True)
    quantity = serializers.IntegerField()
    sale_price = serializers.IntegerField(source='bookinfo.sale_price', read_only=True)
    # 도서관 정보
    library_id = serializers.IntegerField()
    library_name = serializers.CharField(read_only=True)

    class Meta:
        model = UserBook
        fields = (
            'bookinfo', 'title', 'cover', 'quantity',
            'status', 'created_at', 'library_id', 'library_name', 'sale_price'
        )

class MyLibraryModifySerializer(serializers.Serializer):
    library_id = serializers.IntegerField()


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserImage
        fields = "__all__"