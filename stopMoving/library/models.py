from django.db import models

# Create your models here.
class BaseModel(models.Model):
    created = models.DateTimeField(auto_now_add=True) # 생성시간
    updated = models.DateTimeField(auto_now=True) # 수정시간

    class Meta:
        abstract = True

class Library(models.Model):
    name = models.CharField(max_length=50)
    address = models.CharField(max_length=255)
    contact = models.CharField(max_length=50, null=True, blank=True)
    closed_days = models.JSONField(null=True, blank=True)  # 휴관일
    hours_of_use = models.JSONField(null=True, blank=True) # 운영 시간
    sns = models.CharField(max_length=255, null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    long = models.FloatField(null=True, blank=True)
    library_image_url = models.URLField(null=True, max_length=500)    

class LibraryImage(BaseModel):
    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="images")
    id = models.AutoField(primary_key=True)
    image_url = models.URLField(max_length=500)  # S3에 업로드된 이미지의 URL 저장

    def __str__(self):
        return f"Image {self.id}"