# library/migrations/0005_backfill_libraryimage_library.py
from django.db import migrations

def ensure_library_image_url_column(apps, schema_editor):
    # MySQL 5.7/8.0 모두 호환: information_schema 로 존재 여부 확인 후 ADD
    with schema_editor.connection.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'library_library'
              AND COLUMN_NAME = 'library_image_url'
        """)
        (cnt,) = cur.fetchone()
        if cnt == 0:
            cur.execute("ALTER TABLE library_library ADD COLUMN library_image_url VARCHAR(500) NULL")

def backfill_library_fk(apps, schema_editor):
    LibraryImage = apps.get_model('library', 'LibraryImage')
    Library = apps.get_model('library', 'Library')

    # PK만 읽어서 불필요한 컬럼 SELECT 피하기 (library_image_url 문제 회피)
    default_lib_id = Library.objects.order_by('pk').values_list('pk', flat=True).first()
    if default_lib_id is None:
        return
    LibraryImage.objects.filter(library__isnull=True).update(library_id=default_lib_id)

class Migration(migrations.Migration):
    dependencies = [
        ('library', '0004_alter_library_library_image_url_and_more'),
    ]
    operations = [
        # ① 컬럼 보장
        migrations.RunPython(ensure_library_image_url_column, migrations.RunPython.noop),
        # ② 백필
        migrations.RunPython(backfill_library_fk, migrations.RunPython.noop),
    ]
