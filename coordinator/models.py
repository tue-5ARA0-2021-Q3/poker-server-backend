from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

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
    is_test = models.BooleanField(null = False, default = False)
    is_bot = models.BooleanField(null = False, default = False)



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

class WaitingRoomTypes(IntEnum):
    DUEL_PLAYER_BOT              = 1
    DUEL_PLAYER_PLAYER           = 2
    TOURNAMENT_PLAYERS           = 3
    TOURNAMENT_PLAYERS_WITH_BOTS = 4

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]

# Normally before games start coordinator will create a waiting room for players with an arbitrary capacity
# Coordinator will wait for some timeout for all players to connect, close waiting room and depending on the type of waiting room
# and number of connected players closes it or proceeds with games between players
# See also `RoomRegistration`
class WaitingRoom(models.Model):
    id         = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    capacity   = models.IntegerField(validators = [ MinValueValidator(1) ], null = False)
    registered = models.IntegerField(validators = [ MinValueValidator(0) ], default = 0, null = False)
    timeout    = models.IntegerField(validators = [ MinValueValidator(0) ], null = False)
    roomtype   = models.IntegerField(choices = WaitingRoomTypes.choices(), null = False)
    ready      = models.BooleanField(default = False, null = False)
    closed     = models.BooleanField(default = False, null = False)
    error      = models.TextField(null = True)

class RoomRegistration(models.Model):
    id     = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    room   = models.ForeignKey(WaitingRoom, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)


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

