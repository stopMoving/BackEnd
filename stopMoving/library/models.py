from django.db import models

# Create your models here.
class Library(models.Model):
    name = models.CharField(max_length=50)
    address = models.CharField(max_length=255)
    contact = models.CharField(max_length=50, null=True, blank=True)
    closed_days = models.JSONField(null=True, blank=True)  # 휴관일
    hours_of_use = models.JSONField(null=True, blank=True) # 운영 시간
    sns = models.CharField(max_length=255, null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    long = models.FloatField(null=True, blank=True)