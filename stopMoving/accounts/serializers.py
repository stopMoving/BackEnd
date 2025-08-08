from rest_framework import serializers
from .models import User
from rest_framework_simplejwt.serializers import RefreshToken
import re

# 회원가입용 시리얼라이저
class RegisterSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True, required=True)
    password2 = serializers.CharField(write_only=True, required=True)
    username = serializers.CharField(required=True)
    nickname = serializers.CharField(required=True)

    class Meta:
        model = User

        # 필요한 필드값만 지정
        fields = ['username','password1', 'password2', 'nickname']
    
    # create() 재정의
    def create(self, validated_data):
    
        # 비밀번호 분리
        password = validated_data.pop('password1')
        validated_data.pop('password2')  # 필요 없음
        
        # user 객체 생성
        user = User(**validated_data)

        # 비밀번호는 해싱해서 저장
        user.set_password(password)
        user.save()

        return user
    
    # ID 유효성 검사 함수
    def validate_username(self, value):
        
        # ID 길이가 맞는지 검사
        if len(value) < 5 or len(value) > 20:
            raise serializers.ValidationError("아이디는 5자 이상 20자 이하만 가능합니다.")
        # 형식이 맞는지 검사
        if not re.match(r'^[a-z0-9]+$', value):
            raise serializers.ValidationError("아이디는 영문 소문자와 숫자만 사용할 수 있습니다.")
        # ID 중복 여부 검사
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("이미 사용 중인 아이디입니다.")
        
        return value
    
    # 비밀번호 유효성 검사
    def validate_password1(self, value):

        # 비밀번호 길이 맞는지 검사
        if len(value) < 8 or len(value) > 16:
            raise serializers.ValidationError("비밀번호는 8자 이상 16자 이하만 가능합니다.")
        # 비밀번호 형식 맞는지 검사
        if not re.match(r'^[A-Za-z0-9]+$', value):
            raise serializers.ValidationError("비밀번호는 영문 대/소문자와 숫자만 사용 가능합니다.")
        
        return value
    
    # 비밀번호 일치 확인
    def validate(self, data):

        if data['password1'] != data['password2']:
            raise serializers.ValidationError({"비밀번호가 일치하지 않습니다."})
        
        return data
    
    # 닉네임 유효성 검사
    def validate_nickname(self, value):

        # 닉네임 길이 맞는지 검사
        if len(value) < 2 or len(value) > 10:
            raise serializers.ValidationError("닉네임은 2자 이상 10자 이하만 가능합니다.")
        # 닉네임 형식 맞는지 검사
        if not re.match(r'^[A-Za-z가-힣]+$', value):
            raise serializers.ValidationError("닉네임은 한글과 영문 대소문자만 사용할 수 있습니다.")
        # 닉네임 중복 검사
        if User.objects.filter(nickname=value).exists():
            raise serializers.ValidationError("이미 사용 중인 아이디입니다.")
        
        return value
    


# 로그인용 시리얼라이저
class AuthSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)
    
    class Meta:
        model = User

        # 로그인은 username과 password만 필요
        fields = ['username', 'password']

    # 로그인 유효성 검사 함수
    def validate(self, data):
        username = data.get('username', None)
        password = data.get('password', None)
		    
		    # username으로 사용자 찾는 모델 함수
        user = User.get_user_by_username(username=username)
        
        # 존재하는 회원인지 확인
        if user is None:
            raise serializers.ValidationError("User does not exist.")
        else:
			      # 비밀번호 일치 여부 확인
            if not user.check_password(password):
                raise serializers.ValidationError("Wrong password.")
        
        token = RefreshToken.for_user(user)
        refresh_token = str(token)
        access_token = str(token.access_token)

        data = {
            "user": user,
            "refresh_token": refresh_token,
            "access_token": access_token,
        }

        return data


# 로그인용 시리얼라이저
class AuthSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)
    
    class Meta:
        model = User

        # 로그인은 username과 password만 필요
        fields = ['username', 'password']

    # 로그인 유효성 검사 함수
    def validate(self, data):
        username = data.get('username', None)
        password = data.get('password', None)
		    
		# username으로 사용자 찾는 모델 함수
        user = User.get_user_by_username(username=username)
        
        # 존재하는 회원인지 확인
        if user is None:
            raise serializers.ValidationError("ID 혹은 비밀번호를 잘못 입력하셨거나 등록되지 않은 ID입니다.")
        else:
			# 비밀번호 일치 여부 확인
            if not user.check_password(password):
                raise serializers.ValidationError("ID 혹은 비밀번호를 잘못 입력하셨거나 등록되지 않은 ID입니다.")
        
        token = RefreshToken.for_user(user)
        refresh_token = str(token)
        access_token = str(token.access_token)

        data = {
            "user": user,
            "refresh_token": refresh_token,
            "access_token": access_token,
        }

        return data