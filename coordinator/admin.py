from django.contrib import admin

from coordinator.models import Game, UserToken

# Register your models here.
admin.site.register(UserToken)
admin.site.register(Game)
