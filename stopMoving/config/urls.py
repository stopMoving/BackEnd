"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions 
from drf_yasg.views import get_schema_view 
from drf_yasg import openapi

# Swagger 설정
schema_view = get_schema_view(
    openapi.Info(
        title="Post API",
        default_version="v1",
        description="게시글 API 문서",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),  # Swagger 접근 가능하도록 설정
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('posts/', include('posts.urls')),  # posts 앱의 URL 포함
    path('bookinfo/', include('bookinfo.urls')), # bookinfo 앱의 URL 포함
    path('accounts/', include('accounts.urls')), # accounts 앱의 URL 포함
    path('books/', include('books.urls')), # books 앱의 URL 포함
    path('library/', include('library.urls')), # library 앱의 URL 포함
    path('surveys/', include('surveys.urls')), 
    path('recommendations/', include('recommendations.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]