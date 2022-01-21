
from datetime import time
import queue
import threading
import logging
from typing import List
from django.conf import settings
from django.db import transaction
from django.db.models import F

from coordinator.models import GameCoordinator, Player, RoomRegistration, WaitingRoom

# `KuhnWaitingRoom` is a simple abstraction around a set of registered players
# In a normal game mode waiting room capacity is set to 2
# In a tournament mode capacity might be bigger, but this structure does not make any assumptions 
# about what number of players it should hold
# Waiting room registers players and sends an event to a coordinator once lobby is full or after a prespecified timeout
class KuhnWaitingRoom(object):
 
    class WaitingRoomIsFull(Exception):
        pass

    class WaitingRoomIsClosed(Exception):
        pass

    class PlayerDoubleRegistration(Exception):
        pass

    def __init__(self, coordinator, capacity: int, timeout: int):

        dbroom = WaitingRoom(
            coordinator = GameCoordinator.objects.get(id = coordinator.id),
            capacity    = capacity,
            timeout     = timeout
        )
        dbroom.save()

        self.id              = str(dbroom.id)
        self.coordinator     = coordinator
        self.lock            = threading.RLock()
        self.capacity        = capacity
        self.timeout         = timeout
        self.player_channels = {}
        self.disconnected    = {}
        self.ready           = threading.Event()
        self.closed          = False
        self.logger          = logging.getLogger('kuhn.waiting')

        self.logger.info(f'Waiting room { self.id } has been created sucessfully.')
    
    def get_player_tokens(self) -> List[str]:
        with self.lock: 
            return list(self.player_channels.keys())

    def get_player_channel(self, player_token: str) -> queue.Queue:
        with self.lock:
            return self.player_channels[player_token]

    def get_room_capacity(self) -> int:
        return self.capacity

    def get_num_registered_players(self) -> int:
        with self.lock:
            return len(self.player_channels)

    def is_player_registered(self, player_token: str) -> bool:
        with self.lock:
            return player_token in self.player_channels

    def notify_all_players(self, message):
        with self.lock:
            for player_token, player_channel in self.player_channels.items():
                if not self.is_disconnected(player_token):
                    player_channel.put(message)
                    # player_channel.join()

    def wait_ready(self) -> bool:
        return self.ready.wait(timeout = self.timeout)

    def is_ready(self) -> bool:
        with self.lock:
            return self.ready.is_set()

    def mark_as_ready(self) -> bool:
        with self.lock:
            if not self.is_ready():
                WaitingRoom.objects.filter(id = self.id).update(ready = True)
                self.ready.set()

    def mark_as_unready(self):
        with self.lock:
            if self.is_ready():
                WaitingRoom.objects.filter(id = self.id).update(ready = True)
                self.ready.clear()

    def is_closed(self) -> bool:
        with self.lock:
            return self.closed

    def close(self, error = None):
        with self.lock:
            if not self.is_closed():
                WaitingRoom.objects.filter(id = self.id).update(closed = True, error = None if error is None else str(error))
                self.closed = True
                self.ready.set()

    def is_disconnected(self, player_token: str) -> bool:
        with self.lock:
            return self.disconnected[player_token]

    def mark_as_disconnected(self, player_token: str):
        with self.lock:
            self.disconnected[player_token] = True

    def is_registered(self, player_token: str):
        with self.lock:
            return player_token in self.player_channels

    def register_player(self, player_token: str):
        with self.lock:
            # Check if lobby is closed for registrations
            if self.is_ready() or self.is_closed():
                raise KuhnWaitingRoom.WaitingRoomIsClosed('Waiting room is closed for new registrations')

            # Check if lobby is already full or throw an exception otherwise
            if self.get_num_registered_players() >= self.get_room_capacity():
                raise KuhnWaitingRoom.WaitingRoomIsFull('Waiting room is full')

            # Check if player already has been registered for this lobby
            if self.is_player_registered(player_token):
                raise KuhnWaitingRoom.PlayerDoubleRegistration('Player with the same id has been already registered in this waiting room')

            # For each new registration we keep a record in the server's database for logging purposes
            registration = RoomRegistration(
                room = WaitingRoom.objects.get(id = self.id), 
                player = Player.objects.get(token = player_token)
            )

            with transaction.atomic():
                WaitingRoom.objects.filter(id = self.id).update(registered = F('registered') + 1)
                registration.save()

            # For each player we create a separate channel for messages between game coordinator and player
            self.player_channels[player_token] = queue.Queue()
            self.disconnected[player_token] = False

            self.logger.info(f'Player { player_token } has been registered in the waiting room { self.id }')

            # We do not expect the number of registered players to exceed room capacity, however, we do extra check here just to be sure
            # Should be unreachable
            if self.get_num_registered_players() > self.get_room_capacity():
                self.close(error = 'Room capacity exceeded')
                self.logger.warning(f'Waiting room { self.id } has more number of registered players than room capacity')
                return

            # If number of registered players is equal to room capacity we close further registrations and mark room as ready
            if self.get_num_registered_players() == self.get_room_capacity(): 
                self.mark_as_ready()
                self.logger.info(f'Waiting room { self.id } marked as ready.')
                return