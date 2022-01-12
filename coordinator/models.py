from django.db import models
from django.contrib import admin
from enum import IntEnum

import uuid
import random

# Create your models here.
from django.utils.timezone import now

RandomUserNames = [
    'Unique Sandpiper',
    'Crazy Termite',
    'Rubbery Buffalo',
    'Reckless Chamois',
    'Legal Mosquitoe',
    'Ringed Lizard',
    'Fiery Turtledove',
    'Original Racehorse',
    'One Owl',
    'Luminous Marten',
    'Lonely Gelding',
    'Favorite Hawk',
    'Fond Pony',
    'Wide Cod',
    'Ill Hyena',
    'Unguarded Curlew',
    'Yielding Sheldrake',
    'Yellow Ishchimpanzee',
    'Stingy Raven',
    'Wan Lemur',
    'Perfumed Squirrel',
    'Nippy Robin',
    'Sweet Badger',
    'Greedy Goldfinch',
    'Mature Antelope',
    'Leafy Ibis',
    'Puffy Orangutan',
    'Immense Panda',
    'Wise Peafowl',
    'Agonizing Anaconda',
    'Thankful Bloodhound',
    'Special Sparrow',
    'Young Swan',
    'Elastic Ponie',
    'Previous Goose',
    'Disruptive Teal',
    'Pungent Kangaroo',
    'Hidden Pelican',
    'Slovenly Jellyfish',
]


def pick_random_username():
    return random.choice(RandomUserNames)


class Player(models.Model):
    token = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    public_token = models.UUIDField(default = uuid.uuid4, editable = False, null = False)
    name = models.CharField(max_length = 128, null = False, default = pick_random_username)
    email = models.EmailField(null = True)
    is_disabled = models.BooleanField(null = False, editable = True, default = False)


class PlayerAdmin(admin.ModelAdmin):
    list_display = ('token', 'public_token', 'name', 'email', 'is_disabled')
    list_filter = ('token', 'public_token', 'name', 'email', 'is_disabled')
    readonly_fields = ('token', 'public_token')

    class Meta:
        model = Player


class PlayerTypes(IntEnum):
    PLAYER_BOT = 1
    PLAYER_PLAYER = 2

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]

class KuhnTypes(IntEnum):
    CARD3 = 1
    CARD4 = 2

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]


class Game(models.Model):
    id = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    is_started = models.BooleanField(null = False, default = False)
    is_finished = models.BooleanField(null = False, default = False)
    is_failed = models.BooleanField(null = False, default = False)
    is_private = models.BooleanField(null = False, default = False)
    error = models.TextField(null = True)
    created_by = models.UUIDField(null = False)
    created_at = models.DateTimeField(auto_now_add = True)
    player_1 = models.UUIDField(null = True)
    player_2 = models.UUIDField(null = True)
    outcome = models.TextField(default = '')
    winner_id = models.UUIDField(null = True)
    kuhn_type = models.IntegerField(choices = KuhnTypes.choices(), null = False)
    player_type = models.IntegerField(choices = PlayerTypes.choices(), null = False)


class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_started', 'is_finished', 'is_failed', 'is_private', 'created_at', 'player_1', 'player_2', 'winner_id', 'kuhn_type', 'player_type')
    list_filter = ('is_started', 'is_finished', 'is_failed', 'is_private', 'player_1', 'player_2', 'winner_id', 'kuhn_type', 'player_type')

    readonly_fields = ('is_started', 'is_finished', 'is_failed', 'is_private',
                       'error', 'created_by', 'created_at', 'player_1', 'player_2', 'outcome',
                       'winner_id', 'kuhn_type', 'player_type')

    class Meta:
        model = Game


class GameLogTypes(IntEnum):
    INFO = 1
    WARN = 2
    ERROR = 3

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]


class GameLog(models.Model):
    game_id = models.UUIDField(editable = False)
    index = models.IntegerField(null = False, editable = False)
    created_at = models.DateTimeField(default = now, editable = False)
    type = models.IntegerField(choices = GameLogTypes.choices(), null = False)
    content = models.TextField(null = False, editable = False)


class GameLogAdmin(admin.ModelAdmin):
    list_display = ('game_id', 'index', 'time_seconds', 'type', 'content')
    list_filter = ('game_id', 'type')

    readonly_fields = ('game_id', 'index', 'created_at', 'type', 'content')

    class Meta:
        model = Game

    def time_seconds(self, obj):
        return obj.created_at.strftime('%b %d %H:%M:%S.%f')
