from django.db import migrations
from django.conf import settings

def backfill_user_fk(apps, schema_editor):
    # UserImage 모델 가져오기
    UserImage = apps.get_model('users', 'UserImage')

    # AUTH_USER_MODEL 기준으로 사용자 모델 가져오기
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)

    # 기본으로 채울 사용자 하나 선택 (정책에 맞게 수정 가능)
    default_user = User.objects.order_by('pk').first()
    if not default_user:
        return

    # user가 NULL인 레코드들 채우기
    UserImage.objects.filter(user__isnull=True).update(user_id=default_user.pk)

class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0007_userimage_user_userinfo_user_image_url'),
    ]

    operations = [
        migrations.RunPython(backfill_user_fk, migrations.RunPython.noop),
    ]
