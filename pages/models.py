from django.db import models

# Create your models here.

class Announcement(models.Model):
    title      = models.TextField()
    message    = models.TextField()
    created_at = models.DateTimeField(auto_now_add = True)
    is_hidden  = models.BooleanField()
