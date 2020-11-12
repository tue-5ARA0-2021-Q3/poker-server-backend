import threading
import queue
import random

from typing import List

from coordinator.games.kuhn_game import KuhnRootChanceGameState
from coordinator.games.kuhn_constants import CARDS_DEALINGS, NEXT
from coordinator.models import Game


class KuhnGameLobbyStageMessage(object):

    def __init__(self, state, actions):
        self.state = state
        self.actions = actions


class KuhnGameLobbyStageError(object):

    def __init__(self, error):
        self.error = error


class KuhnGameLobbyPlayerMessage(object):

    def __init__(self, player_id, action):
        self.player_id = player_id
        self.action = action


class KuhnGameLobbyPlayer(object):

    def __init__(self, player_id: int, bank: int):
        self.player_id = player_id
        self.bank = bank
        self.channel = queue.Queue()

    def send_message(self, message: KuhnGameLobbyStageMessage):
        self.channel.put(message)

    def send_error(self, error: KuhnGameLobbyStageError):
        self.channel.put(error)


class KuhnGameLobbyStage(object):

    def __init__(self, lobby):
        self._root = KuhnRootChanceGameState(CARDS_DEALINGS)
        self._stage = self._root.play(random.choice(CARDS_DEALINGS))
        self._cards = self._stage.cards

    def cards(self):
        return self._cards

    def card(self, index):
        return self._cards[index]

    def actions(self):
        return self._stage.actions

    def play(self, action):
        self._stage = self._stage.play(action)

    def is_terminal(self):
        return self._stage.is_terminal()

    def inf_set(self):
        return self._stage.inf_set()

    def secret_inf_set(self):
        return self._stage.secret_inf_set()


class KuhnGameLobby(object):
    InitialBank = 5
    MessagesTimeout = 5

    def __init__(self, game_id: str):
        self.lock = threading.Lock()
        self.game_id = game_id
        self.stages = []
        self.channel = queue.Queue()

        # private fields
        self._closed = threading.Event()
        self._lobby_coordinator_thread = None
        self._player_connection_barrier = threading.Barrier(3)

        self._players = {}
        self._player_opponent = {}

    def close(self):
        with self.lock:
            self._closed.set()

    def is_closed(self) -> bool:
        with self.lock:
            return self._closed.is_set()

    def get_players(self) -> List[KuhnGameLobbyPlayer]:
        return list(self._players.values())

    def get_player(self, player_id: str) -> KuhnGameLobbyPlayer:
        return self._players[player_id]

    def get_player_ids(self) -> List[str]:
        return list(self._players.keys())

    def get_num_players(self) -> int:
        return len(self.get_player_ids())

    def get_player_opponent(self, player_id: str) -> str:
        return self._player_opponent[player_id]

    def get_player_channel(self, player_id: str) -> queue.Queue:
        return self._players[player_id].channel

    def get_random_player_id(self) -> str:
        return random.choice(list(self._players.keys()))

    def start(self):
        # First player which hits this function starts a separate thread with a game coordinator
        # Ref: play_lobby(lobby)
        with self.lock:
            if self._lobby_coordinator_thread is None:
                self._lobby_coordinator_thread = threading.Thread(target = game_lobby_coordinator,
                                                                  args = (self, KuhnGameLobby.MessagesTimeout))
                self._lobby_coordinator_thread.start()

    def register_player(self, player_id: int):
        with self.lock:
            # Check if lobby is already full or throw an exception otherwise
            if self.get_num_players() >= 2:
                raise Exception('Game lobby is full')

            # For each player we create a separate channel for messages between game coordinator and player
            self._players[player_id] = KuhnGameLobbyPlayer(player_id, bank = KuhnGameLobby.InitialBank)

            # If both players are connected we set corresponding ids to self._player_opponent dictionary for easy lookup
            if self.get_num_players() == 2:
                player_ids = self.get_player_ids()
                player1_id, player2_id = player_ids[0], player_ids[1]

                self._player_opponent[player1_id] = player2_id
                self._player_opponent[player2_id] = player1_id

                # Update database entry of the game with corresponding player ids and mark it as started
                game_db = Game.objects.get(id = self.game_id)
                game_db.player_1 = player1_id
                game_db.player_2 = player2_id
                game_db.is_started = True
                game_db.save(update_fields = ['player_1', 'player_2', 'is_started'])

    def wait_for_players(self):
        try:
            self._player_connection_barrier.wait(timeout = 120)
        except threading.BrokenBarrierError:
            raise Exception('Timeout waiting for another player to connect')


def game_lobby_coordinator(lobby: KuhnGameLobby, messages_timeout: int):
    lobby.wait_for_players()

    try:
        stage = KuhnGameLobbyStage(lobby)

        players = lobby.get_players()
        player_id_turn = lobby.get_random_player_id()

        for player in players:
            if player.player_id == player_id_turn:
                player.send_message(KuhnGameLobbyStageMessage(f'{stage.card(0)}', stage.actions()))
            else:
                player.send_message(KuhnGameLobbyStageMessage(f'{stage.card(1)}', ['WAIT']))

        while not lobby.is_closed() or not lobby.channel.empty():
            try:
                message = lobby.channel.get(timeout = messages_timeout)

                print(f'Received a message: {message}')

                if message.player_id == player_id_turn:
                    stage.play(message.action)

                    if stage.is_terminal():
                        for player in players:
                            player.send_message(KuhnGameLobbyStageMessage(f'END:{stage.inf_set()}', ['END']))
                        lobby.close()
                    else:
                        player_id_turn = lobby.get_player_opponent(player_id_turn)
                        lobby.get_player(player_id_turn).send_message(KuhnGameLobbyStageMessage(stage.secret_inf_set(), stage.actions()))
                elif message.action == 'START' or message.action == 'WAIT':
                    continue
                else:
                    print(f'Warn: unexpected message: {message}')
                    continue

            except queue.Empty:
                raise Exception(f'There was no message from a player for more than {messages_timeout} sec.')

    except Exception as e:
        for player in lobby.get_players():
            # noinspection PyBroadException
            try:
                player.send_error(KuhnGameLobbyStageError(e))
            except Exception:
                pass
