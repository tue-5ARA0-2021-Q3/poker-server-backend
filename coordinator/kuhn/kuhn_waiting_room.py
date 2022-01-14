
import queue
import threading
import logging
from typing import List
from django.conf import settings
from django.db import transaction
from django.db.models import F

from coordinator.kuhn.kuhn_player import KuhnGameLobbyPlayer
from coordinator.models import Player, RoomRegistration, WaitingRoom

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

    def __init__(self, room_id:str, room_type:int, capacity:int, timeout = settings.LOBBY_CONNECTION_TIMEOUT):
        self.room_id         = room_id
        self.room_type       = room_type
        self.lock            = threading.RLock()
        self.capacity        = capacity
        self.timeout         = timeout
        self.player_channels = {}
        self.ready           = threading.Event()
        self.closed          = False
        self.logger          = logging.getLogger('kuhn.waiting')
    
    def get_player_ids(self) -> List[str]:
        with self.lock: 
            return list(self.player_channels.keys())

    def get_player_channel(self, player_id: str) -> queue.Queue:
        with self.lock:
            return self.player_channels[player_id]

    def get_room_capacity(self) -> int:
        return self.capacity

    def get_num_registered_players(self) -> int:
        with self.lock:
            return len(self.player_channels)

    def is_player_registered(self, player_id: str) -> bool:
        with self.lock:
            return player_id in self.player_channels

    def wait_ready(self) -> bool:
        return self.ready.wait(timeout = self.timeout)

    def is_ready(self) -> bool:
        with self.lock:
            return self.ready.is_set()

    def mark_as_ready(self) -> bool:
        with self.lock:
            if not self.is_ready():
                WaitingRoom.objects.get(id = self.room_id).update(ready = True)
                self.ready.set()

    def is_closed(self) -> bool:
        with self.lock:
            return self.is_closed

    def close(self, error = None):
        with self.lock:
            if not self.is_closed():
                WaitingRoom.objects.get(id = self.room_id).update(closed = True, error = error)
                self.closed = True
                self.ready.set()

    def register_player(self, player_id: str):
        with self.lock:
            # Check if lobby is closed for registrations
            if self.is_ready() or self.is_closed():
                raise KuhnWaitingRoom.WaitingRoomIsClosed('Waiting room is closed for new registrations')

            # Check if lobby is already full or throw an exception otherwise
            if self.get_num_registered_players() >= self.get_room_capacity():
                raise KuhnWaitingRoom.WaitingRoomIsFull('Waiting room is full')

            # Check if player already has been registered for this lobby
            if self.is_player_registered(player_id):
                raise KuhnWaitingRoom.PlayerDoubleRegistration('Player with the same id has been already registered in this waiting room')

            # For each new registration we keep a record in the server's database for logging purposes
            registration = RoomRegistration(
                room = WaitingRoom.objects.get(id = self.room_id), 
                player = Player.objects.get(id = player_id)
            )

            with transaction.atomic():
                WaitingRoom.objects.get(id = self.room_id).update(registered = F('registered') + 1)
                registration.save()

            # For each player we create a separate channel for messages between game coordinator and player
            self.player_channels[player_id] = queue.Queue()

            self.logger.info(f'Player { player_id } has been registered in the waiting room { self.room_id }')

            # We do not expect the number of registered players to exceed room capacity, however, we do extra check here just to be sure
            # Should be unreachable
            if self.get_num_registered_players() > self.get_room_capacity():
                self.close(error = 'Room capacity exceeded')
                self.logger.warning(f'Waiting room { self.room_id } has more number of registered players than room capacity')
                return

            # If number of registered players is equal to room capacity we close further registrations and mark room as ready
            if self.get_num_registered_players() == self.get_room_capacity(): 
                self.mark_as_ready()
                self.logger.info(f'Waiting room { self.room_id } marked as ready.')
                return


            # TODO move to coordinator
            # if self.get_num_players() == 1:
            #     player_ids = self.get_player_ids()
            #     player1_id = player_ids[0]

            #     game_db = Game.objects.get(id = self.game_id)
            #     game_db.player_1 = player1_id
            #     game_db.save(update_fields = ['player_1'])

            # TODO move to coordinator
            # If we have one player connected to the lobby and lobby type is PLAYER_BOT we initiate new thread for a bot player
            # if self.get_num_players() == 1 and self.player_type == PlayerTypes.PLAYER_BOT:
            #     if self._lobby_bot_thread is None:
            #         self._logger.info(f'Lobby {self.game_id} attempts to add a bot')
            #         bot_players = Player.objects.filter(is_bot = True)
            #         if len(bot_players) == 0:
            #             raise Exception('Could not find a bot player to play against')
            #         bot_player = bot_players[0]
            #         bot_token  = str(bot_player.token)
            #         if len(KuhnGameLobby.LobbyBots) == 0:
            #             raise Exception('Server has no bot implementations available.')
            #         bot_exec   = str(random.choice(KuhnGameLobby.LobbyBots))
            #         self._lobby_bot_thread = threading.Thread(target = game_bot, args = (self, bot_token, bot_exec, KuhnGameLobby.BotCreationDelay))
            #         self._lobby_bot_thread.start()
            #         self._logger.info('Lobby bot thread has been created')

            # TODO move to coordinator
            # If both players are connected we set corresponding ids to self._player_opponent dictionary for easy lookup
            # if self.get_num_players() == 2:
            #     player_ids = self.get_player_ids()
            #     player1_id, player2_id = player_ids[0], player_ids[1]

            #     self._player_opponent[player1_id] = player2_id
            #     self._player_opponent[player2_id] = player1_id

            #     # Update database entry of the game with corresponding player ids and mark it as started
            #     game_db = Game.objects.get(id = self.game_id)
            #     game_db.player_1 = player1_id
            #     game_db.player_2 = player2_id
            #     game_db.is_started = True
            #     game_db.save(update_fields = ['player_1', 'player_2', 'is_started'])
            #     self._logger.info(f'The game has been started')