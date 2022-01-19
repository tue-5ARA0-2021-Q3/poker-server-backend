from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

from enum import IntEnum

import itertools
import uuid
import random

# Create your models here.
from django.utils.timezone import now

from coordinator.kuhn.kuhn_constants import CARD3, CARD4

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
    token        = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    public_token = models.UUIDField(default = uuid.uuid4, editable = False, null = False)
    name         = models.CharField(max_length = 128, null = False, default = pick_random_username)
    email        = models.EmailField(null = True)
    is_disabled  = models.BooleanField(null = False, editable = True, default = False)
    is_test      = models.BooleanField(null = False, default = False)
    is_bot       = models.BooleanField(null = False, default = False)


class PlayerTypes(IntEnum):
    PLAYER_BOT = 1
    PLAYER_PLAYER = 2

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]

class GameTypes(IntEnum):
    KUHN_CARD3 = CARD3
    KUHN_CARD4 = CARD4

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]

# Game coordinator support different types of game scheduling
# DUEL type spawns a single game between two players
# TOURNAMENT type may spawn multiple games between many players
class GameCoordinatorTypes(IntEnum):
    DUEL_PLAYER_BOT              = 1
    DUEL_PLAYER_PLAYER           = 2
    TOURNAMENT_PLAYERS           = 3
    TOURNAMENT_PLAYERS_WITH_BOTS = 4

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]

# GameCoordinator simply holds information about type of game scheduling, actual game being played and creation timestamp
# It also contains recent status of coordinator itself, like `is_started`, `is_finished` or `is_failed`
# Before starting a game players should connect to a coordinator with a specific id or just a random coordinator
class GameCoordinator(models.Model):
    id               = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    coordinator_type = models.IntegerField(choices = GameCoordinatorTypes.choices(), null = False)
    is_started       = models.BooleanField(null = False, default = False)
    is_finished      = models.BooleanField(null = False, default = False)
    is_failed        = models.BooleanField(null = False, default = False)
    is_private       = models.BooleanField(null = False)
    created_at       = models.DateTimeField(auto_now_add = True)
    game_type        = models.IntegerField(choices = GameTypes.choices(), null = False)
    error            = models.TextField(null = True)

# Normally before games start coordinator will create a waiting room for players with an arbitrary capacity
# Coordinator will wait for some timeout for all players to connect, close waiting room and depending on the type of waiting room
# and number of connected players closes it or proceeds with games between players
# See also `RoomRegistration`
class WaitingRoom(models.Model):
    id          = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    coordinator = models.OneToOneField(GameCoordinator, on_delete = models.CASCADE, null = False)
    capacity    = models.IntegerField(validators = [ MinValueValidator(1) ], null = False)
    registered  = models.IntegerField(validators = [ MinValueValidator(0) ], default = 0, null = False)
    timeout     = models.IntegerField(validators = [ MinValueValidator(0) ], null = False)
    ready       = models.BooleanField(default = False, null = False)
    closed      = models.BooleanField(default = False, null = False)
    error       = models.TextField(null = True)

class RoomRegistration(models.Model):
    id     = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    room   = models.ForeignKey(WaitingRoom, on_delete = models.CASCADE, null = False)
    player = models.ForeignKey(Player, on_delete = models.CASCADE, null = False)


class Game(models.Model):
    id = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    is_started  = models.BooleanField(null = False, default = False)
    is_finished = models.BooleanField(null = False, default = False)
    is_failed   = models.BooleanField(null = False, default = False)
    error       = models.TextField(null = True)
    created_by  = models.ForeignKey(GameCoordinator, on_delete = models.CASCADE, null = False)
    created_at  = models.DateTimeField(auto_now_add = True)
    player1     = models.ForeignKey(Player, on_delete = models.CASCADE, null = False, related_name = 'games_player1')
    player2     = models.ForeignKey(Player, on_delete = models.CASCADE, null = False, related_name = 'games_player2')
    winner      = models.ForeignKey(Player, on_delete = models.CASCADE, null = True, related_name = 'games_winner')
    game_type   = models.IntegerField(choices = GameTypes.choices(), null = False)

class GameRound(models.Model):
    id          = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    game        = models.ForeignKey(Game, on_delete = models.CASCADE, null = False)
    first       = models.ForeignKey(Player, on_delete = models.CASCADE, null = False, related_name = 'rounds_first')
    second      = models.ForeignKey(Player, on_delete = models.CASCADE, null = False, related_name = 'rounds_second')
    index       = models.IntegerField(validators = [ MinValueValidator(1) ])
    cards       = models.CharField(max_length = 2, null = True)
    inf_set     = models.CharField(max_length = 128, null = True)
    evaluation  = models.IntegerField(null = True)

    def actions(self):
        return zip(self.inf_set.split('.')[2:], itertools.cycle([ self.first, self.second ])) if self.inf_set is not None else None


class Tournament(models.Model):
    id          = models.UUIDField(primary_key = True, default = uuid.uuid4, editable = False)
    coordinator = models.ForeignKey(GameCoordinator, on_delete = models.CASCADE, null = True)
    place1      = models.ForeignKey(Player, on_delete = models.CASCADE, null = True, related_name = 'places_1')
    place2      = models.ForeignKey(Player, on_delete = models.CASCADE, null = True, related_name = 'places_3')
    place3      = models.ForeignKey(Player, on_delete = models.CASCADE, null = True, related_name = 'places_2')
    timeout     = models.IntegerField(validators = [ MinValueValidator(1) ], null = False)
    capacity    = models.IntegerField(validators = [ MinValueValidator(3) ], null = False)
    game_type   = models.IntegerField(choices = GameTypes.choices(), null = False)
    allow_bots  = models.BooleanField(null = False, default = True)
    is_started  = models.BooleanField(null = False, default = False)