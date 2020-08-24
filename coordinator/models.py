from django.db import models

import uuid
# Create your models here.

class UserToken(models.Model):
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name  = models.CharField(max_length=128, null=True)
    email = models.EmailField(null=True)

class Game(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_started = models.BooleanField(null=False, default=False)
    is_ended   = models.BooleanField(null=False, default=False)
    created_by = models.UUIDField(null=False)