from django.db import models
from django.contrib import admin
from enum import IntEnum
import uuid


# Create your models here.

class Player(models.Model):
    token = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    name = models.CharField(max_length = 128, null = True)
    email = models.EmailField(null = True)


class GameTypes(IntEnum):
    PLAYER_BOT = 1
    PLAYER_PLAYER = 2

    @classmethod
    def choices(cls):
        return [ (key.value, key.name) for key in cls ]


class Game(models.Model):
    id = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    is_started = models.BooleanField(null = False, default = False)
    is_finished = models.BooleanField(null = False, default = False)
    is_failed = models.BooleanField(null = False, default = False)
    error = models.TextField(null = True)
    created_by = models.UUIDField(null = False)
    created_at = models.DateTimeField(auto_now_add = True)
    player_1 = models.UUIDField(null = True)
    player_2 = models.UUIDField(null = True)
    outcome = models.TextField(default = '')
    winner_id = models.UUIDField(null = True)
    game_type = models.IntegerField(choices = GameTypes.choices(), null = False)


class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_started', 'is_finished', 'is_failed', 'created_at', 'player_1', 'player_2',
                    'winner_id', 'game_type')
    readonly_fields = ('is_started', 'is_finished', 'is_failed',
                       'error', 'created_by', 'created_at', 'player_1', 'player_2', 'outcome',
                       'winner_id', 'game_type')

    class Meta:
        model = Game
