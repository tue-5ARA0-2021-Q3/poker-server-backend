
import threading
from typing import List
from django.conf import settings

from coordinator.games.kuhn_player import KuhnGameLobbyPlayer

# `KuhnWaitingRoom` is a simple abstraction around a set of registered players
# In a normal game mode waiting room capacity is set to 2
# In a tournament mode capacity might be bigger, but this structure does not make any assumptions 
# about what number of players it should hold
# Waiting room registers players and sends an event to a coordinator once lobby is full or after a prespecified timeout
class KuhnWaitingRoom(object):

    def __init__(self, capacity:int, timeout = settings.LOBBY_CONNECTION_TIMEOUT):
        self.lock     = threading.Lock()
        self.capacity = capacity
        self.timeout  = timeout
        self.players  = {}
        self.ready    = threading.Event()

    def get_players(self) -> List[KuhnGameLobbyPlayer]:
        return list(self.players.values())
    
    def get_player_ids(self) -> List[str]:
        return list(self.players.keys())

    def get_player(self, player_id: str) -> KuhnGameLobbyPlayer:
        return self.players[player_id]

    def get_room_capacity(self) -> int:
        return self.capacity

    def get_num_registered_players(self) -> int:
        return len(self.get_player_ids())

    def is_player_registered(self, player_id: str) -> bool:
        return player_id in self.get_player_ids()

    def wait_ready(self) -> bool:
        return self.ready.wait(timeout = self.timeout)