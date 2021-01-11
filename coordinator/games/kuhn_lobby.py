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

    def __init__(self, player_id: str, bank: int):
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
        _inf_set = self._stage.inf_set()
        _, cards, *moves = _inf_set.split('.')
        # We return showdown only in case of last action was CALL
        _cards = cards if moves[-1] == 'CALL' else '??'
        return f'{_}.{_cards}.{".".join(moves)}'  # self._stage.inf_set()

    def secret_inf_set(self):
        return self._stage.secret_inf_set()

    def evaluation(self):
        return self._stage.evaluation()


class KuhnGameRound(object):

    def __init__(self, lobby, first_player = None):
        self.lobby = lobby
        self.stage = KuhnGameLobbyStage(lobby)
        self.started = {}
        self.evaluation = 0
        self.is_evaluated = False
        if first_player is None:
            self.first_player = lobby.get_random_player_id()
        else:
            self.first_player = first_player
        self.player_id_turn = self.first_player


class KuhnGameLobby(object):
    InitialBank = 5
    MessagesTimeout = 5

    class GameLobbyFullError(Exception):
        pass

    class PlayerAlreadyExistError(Exception):
        pass

    def __init__(self, game_id: str):
        self.lock = threading.Lock()
        self.game_id = game_id
        self.rounds = []
        self.channel = queue.Queue()

        # private fields
        self._closed = threading.Event()
        self._lobby_coordinator_thread = None
        self._player_connection_barrier = threading.Barrier(3)

        self._players = {}
        self._player_opponent = {}

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

    def get_winner_id(self) -> str:
        for player in self.get_players():
            if player.bank <= 0:
                return self.get_player_opponent(player.player_id)
        return ''

    def get_outcomes(self) -> str:
        return '|'.join(list(map(lambda _round: f'{_round.stage.inf_set()}:{_round.evaluation}', self.rounds[0:-1])))

    def start(self):
        # First player which hits this function starts a separate thread with a game coordinator
        # Ref: play_lobby(lobby)
        with self.lock:
            if self._lobby_coordinator_thread is None:
                self._lobby_coordinator_thread = threading.Thread(target = game_lobby_coordinator,
                                                                  args = (self, KuhnGameLobby.MessagesTimeout))
                self._lobby_coordinator_thread.start()

    def is_player_registered(self, player_id: str) -> bool:
        return player_id in self.get_player_ids()

    def register_player(self, player_id: str):
        with self.lock:
            # Check if lobby is already full or throw an exception otherwise
            if self.get_num_players() >= 2:
                raise KuhnGameLobby.GameLobbyFullError('Game lobby is full')

            if self.is_player_registered(player_id):
                raise KuhnGameLobby.PlayerAlreadyExistError('Player with the same id is already exist in this lobby')

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

    def get_last_round(self):
        return self.rounds[-1] if len(self.rounds) >= 1 else None

    def create_new_round(self):
        last_round = self.get_last_round()
        # Check if there was a round already and check if it was terminated
        # Throw an error instead, in reality this error should never be raised since game coordinator
        # creates a new round only on termination
        if last_round is None or last_round.stage.is_terminal():
            _first_player = self.get_player_opponent(last_round.first_player) if last_round is not None else None
            _round = KuhnGameRound(self, first_player = _first_player)
            self.rounds.append(_round)
            return _round
        else:
            raise Exception('It is not allowed to start a new round while previous one is not completed')

    def start_new_round(self, player_id):
        # This function starts a new round for each player
        # If player repeatedly sends 'START' messages this function won't do anything until a new round is created
        last_round = self.get_last_round()

        # Check if player already started this round and exit if it is ture
        if player_id in last_round.started and last_round.started[player_id] is True:
            return

        player = self.get_player(player_id)
        last_round.started[player_id] = True

        # First player (last_round.player_id_turn) starts the round so it receives a proper list of available actions
        # Second player just waits
        if player.player_id == last_round.player_id_turn:
            player.send_message(KuhnGameLobbyStageMessage(f'CARD:1:{last_round.stage.card(0)}', last_round.stage.actions()))
        else:
            player.send_message(KuhnGameLobbyStageMessage(f'CARD:2:{last_round.stage.card(1)}', ['WAIT']))

    def evaluate_round(self):
        # This function evaluate a round's outcome at the terminal stage
        # Does nothing if stage is not terminal
        # Does nothing on subsequent evaluations
        with self.lock:
            last_round = self.get_last_round()

            if last_round is None or not last_round.stage.is_terminal():
                return

            if last_round.is_evaluated:
                return

            evaluation = last_round.stage.evaluation()
            for player in self.get_players():
                if last_round.first_player == player.player_id:
                    player.bank = player.bank + evaluation
                else:
                    player.bank = player.bank - evaluation

            last_round.evaluation = evaluation
            last_round.is_evaluated = True

    def convert_evaluation(self, evaluation, player_id):
        with self.lock:
            last_round = self.get_last_round()
            if last_round.first_player == player_id:
                return evaluation
            else:
                return -evaluation

    def check_players_bank(self):
        # Check if lobby can create a new round
        # True if both players have enough bank
        # False otherwise
        can_continue = True
        for player in self.get_players():
            if player.bank <= 0:
                can_continue = False
        return can_continue

    def player_outcome(self, player_id):
        player = self.get_player(player_id)
        if player.bank <= 0:
            return 'DEFEAT'
        else:
            return 'WIN'

    def finish(self, error = None):
        if not self.is_finished():
            with self.lock:
                self._closed.set()
                try:
                    game_db = Game.objects.get(id = self.game_id)
                    if error is None:
                        game_db.is_finished = True
                        game_db.winner_id = self.get_winner_id()
                        game_db.outcome = self.get_outcomes()
                        game_db.save(update_fields = ['is_finished', 'winner_id', 'outcome'])
                    else:
                        game_db.is_failed = True
                        game_db.error = error
                        game_db.save(update_fields = ['is_failed', 'error'])
                except Exception as e:
                    print("Unexpected error: ", e)

    def is_finished(self) -> bool:
        with self.lock:
            return self._closed.is_set()


def game_lobby_coordinator(lobby: KuhnGameLobby, messages_timeout: int):
    try:
        # In the beginning of the session lobby waits for both players to be connected
        # Throws an error if second player did not connect in some reasonable amount of time (check wait_for_players() function)
        lobby.wait_for_players()

        # Once both players are connected lobby creates an initial round and
        # starts this round automatically without waiting for players confirmation
        # On next rounds game coordinator will wait for both players to start a new round explicitly via 'START' action
        current_round = lobby.create_new_round()
        for player in lobby.get_players():
            lobby.start_new_round(player.player_id)

        # TODO
        games_counter = 1

        # We run an inner cycle until lobby is closed or to process last messages after lobby has been closed
        while not lobby.is_finished() or not lobby.channel.empty():
            try:
                # Game coordinator waits for a message from any player
                message = lobby.channel.get(timeout = messages_timeout)

                # First we check if the message is about to start a new round
                # It is possible for a player to send multiple 'START' actions for a single round, but they won't have any effect
                if message.action == 'START':
                    if lobby.check_players_bank():
                        lobby.start_new_round(message.player_id)
                    else:
                        for player in lobby.get_players():
                            player.send_message(KuhnGameLobbyStageMessage(lobby.player_outcome(player.player_id), []))
                        lobby.finish()
                # If message action is not 'START' we check that the message came from a player and assume it is their next action
                elif message.player_id == current_round.player_id_turn:
                    # We register current player's action in an inner stage object
                    current_round.stage.play(message.action)

                    if current_round.stage.is_terminal():
                        # If the stage is terminal we notify both players and start a new round if both players have non-negative bank
                        # TODO
                        for player in lobby.get_players():
                            player.send_message(
                                KuhnGameLobbyStageMessage(
                                    f'END:{lobby.convert_evaluation(current_round.stage.evaluation(), player.player_id)}:{current_round.stage.inf_set()}',
                                    ['START']
                                )
                            )
                        lobby.evaluate_round()
                        current_round = lobby.create_new_round()
                    else:
                        # If the stage is not terminal we swap current's player id and wait for a new action of second player
                        current_round.player_id_turn = lobby.get_player_opponent(current_round.player_id_turn)
                        lobby.get_player(current_round.player_id_turn).send_message(
                            KuhnGameLobbyStageMessage(current_round.stage.secret_inf_set(), current_round.stage.actions())
                        )
                # Wait is an utility message
                elif message.action == 'WAIT':
                    continue
                else:
                    print(f'Warn: unexpected message from player_id = {message.player_id}: [ action = {message.action} ]')
                    continue

            except queue.Empty:
                raise Exception(f'There was no message from a player for more than {messages_timeout} sec.')

    except Exception as e:
        for player in lobby.get_players():
            # noinspection PyBroadException
            try:
                print(f'Exception: {e}')
                player.send_error(KuhnGameLobbyStageError(e))
            except Exception:
                pass
        lobby.finish(error = e)
    finally:
        lobby.finish()
