import time
import threading
import queue
import random
import os
import subprocess

from typing import List, Union
from django.conf import settings

from coordinator.games.kuhn_game import KuhnRootChanceGameState
from coordinator.games.kuhn_constants import KUHN_TYPES, CARDS_DEALINGS, POSSIBLE_CARDS
from coordinator.models import Game, Player, PlayerTypes
from coordinator.utilities.logger import GameActionsLogger


class KuhnGameLobbyStageCardDeal(object):

    def __init__(self, card, turn_order, actions):
        self.card = card
        self.turn_order = turn_order
        self.actions = actions

    def __str__(self):
        return f'message(card = {self.card}, order = {self.turn_order}, actions = {self.actions})'


class KuhnGameLobbyStageMessage(object):

    def __init__(self, state, actions):
        self.state = state
        self.actions = actions

    def __str__(self):
        return f'message(state = {self.state}, actions = {self.actions})'


class KuhnGameLobbyStageError(object):

    def __init__(self, error):
        self.error = error

    def __str__(self):
        return f'message(error = {self.error})'


class KuhnGameLobbyPlayerMessage(object):

    def __init__(self, player_id, action):
        self.player_id = player_id
        self.action = action


class KuhnGameLobbyPlayer(object):

    def __init__(self, player_id: str, bank: int, lobby):
        self.player_id = player_id
        self.bank = bank
        self.channel = queue.Queue()
        self.lobby = lobby

    def send_message(self, message: Union[KuhnGameLobbyStageMessage, KuhnGameLobbyStageCardDeal]):
        self.channel.put(message)
        self.lobby.get_logger().info(f'Player {self.player_id} received {str(message)}')

    def send_error(self, error: KuhnGameLobbyStageError):
        self.channel.put(error)
        self.lobby.get_logger().error(f'Player {self.player_id} received {str(error)}')


class KuhnGameLobbyStage(object):

    def __init__(self, lobby):
        card_dealings = lobby.get_card_dealings()
        self._root  = KuhnRootChanceGameState(card_dealings)
        self._stage = self._root.play(random.choice(card_dealings))
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
        # We return showdown only in case if last action was CALL or both actions was 'CHECK'
        _cards = '??'
        if (moves[-1] == 'CALL') or (moves == ['CHECK', 'CHECK']):
            _cards = cards
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
    InitialBank = settings.LOBBY_INITIAL_BANK
    MessagesTimeout = settings.LOBBY_WAITING_TIMEOUT
    BotCreationDelay = settings.BOT_CREATION_DELAY
    LobbyBots = []

    # Here we check is bots are enabled in server settings
    # Routine picks up `BOT_FOLDER` setting variable, iterates over subfolders,
    # checks for main.py, and adds bot executables paths in `GameCoordinatorService.game_bots`
    if settings.ALLOW_BOTS:
        for folder in os.listdir(settings.BOT_FOLDER):
            bot_exec = os.path.join(settings.BOT_FOLDER, folder, 'main.py')
            if os.path.isfile(bot_exec):
                print('Bot found: ', folder)
                LobbyBots.append(bot_exec)
        

    class GameLobbyFullError(Exception):
        pass

    class PlayerAlreadyExistError(Exception):
        pass

    class PlayerDisconnected(Exception):
        pass

    def __init__(self, game_id: str, kuhn_type: int, player_type: int):
        self.lock = threading.Lock()
        self.game_id = game_id
        self.rounds = []
        self.channel = queue.Queue()
        self.kuhn_type = kuhn_type
        self.player_type = player_type

        if player_type == PlayerTypes.PLAYER_BOT and not settings.ALLOW_BOTS:
            raise Exception('Playing with bots is disallowed in server settings')

        # private fields
        self._closed = threading.Event()
        self._lobby_coordinator_thread = None
        self._lobby_bot_thread = None
        self._player_connection_barrier = threading.Barrier(3)

        self._players = {}
        self._player_opponent = {}
        self._logger = GameActionsLogger(game_id)

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

    def get_logger(self):
        return self._logger

    def get_valid_card_ranks(self):
        return POSSIBLE_CARDS[self.kuhn_type]

    def get_card_dealings(self):
        return CARDS_DEALINGS[self.kuhn_type]

    def start(self):
        # First player which hits this function starts a separate thread with a game coordinator
        # Ref: play_lobby(lobby)
        with self.lock:
            if self._lobby_coordinator_thread is None:
                self._lobby_coordinator_thread = threading.Thread(target = game_lobby_coordinator,
                                                                  args = (self, KuhnGameLobby.MessagesTimeout))
                self._lobby_coordinator_thread.start()
                self._logger.info('Lobby coordinator thread has been created')

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
            self._players[player_id] = KuhnGameLobbyPlayer(player_id, bank = KuhnGameLobby.InitialBank, lobby = self)
            self._logger.info(f'Player {player_id} has been registered in the lobby { self.game_id }')

            if self.get_num_players() == 1:
                player_ids = self.get_player_ids()
                player1_id = player_ids[0]

                game_db = Game.objects.get(id = self.game_id)
                game_db.player_1 = player1_id
                game_db.save(update_fields = ['player_1'])

            # If we have one player connected to the lobby and lobby type is PLAYER_BOT we initiate new thread for a bot player
            if self.get_num_players() == 1 and self.player_type == PlayerTypes.PLAYER_BOT:
                if self._lobby_bot_thread is None:
                    self._logger.info(f'Lobby {self.game_id} attempts to add a bot')
                    bot_players = Player.objects.filter(is_bot = True)
                    if len(bot_players) == 0:
                        raise Exception('Could not find a bot player to play against')
                    bot_player = bot_players[0]
                    bot_token  = str(bot_player.token)
                    bot_exec   = str(random.choice(KuhnGameLobby.LobbyBots))
                    self._lobby_bot_thread = threading.Thread(target = game_bot, args = (self, bot_token, bot_exec, KuhnGameLobby.BotCreationDelay))
                    self._lobby_bot_thread.start()
                    self._logger.info('Lobby bot thread has been created')

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
                self._logger.info(f'The game has been started')

    def wait_for_players(self):
        try:
            self._player_connection_barrier.wait(timeout = settings.LOBBY_CONNECTION_TIMEOUT)
        except threading.BrokenBarrierError:
            self._logger.error('Timeout waiting for another player to connect')
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
            self._logger.info(f'A new round has been created. First player is {_first_player}')
            return _round
        else:
            self._logger.error('It is not allowed to start a new round while previous one is not completed')
            raise Exception('It is not allowed to start a new round while previous one is not completed')

    def start_new_round(self, player_id):
        # This function starts a new round for each player
        # If player repeatedly sends 'START' messages this function won't do anything until a new round is created
        last_round = self.get_last_round()

        # Check if player already started this round and exit if it is true
        if player_id in last_round.started and last_round.started[player_id] is True:
            return

        player = self.get_player(player_id)
        last_round.started[player_id] = True

        self._logger.info(f'{player_id} accepted a new round')

        # First player (last_round.player_id_turn) starts the round so it receives a proper list of available actions
        # Second player just waits
        if player.player_id == last_round.player_id_turn:
            player.send_message(KuhnGameLobbyStageCardDeal(last_round.stage.card(0), '1', last_round.stage.actions()))
        else:
            player.send_message(KuhnGameLobbyStageCardDeal(last_round.stage.card(1), '2', ['WAIT']))

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

            self._logger.info(f'Round has been evaluated. Banks: {list(map(lambda p: p.bank, self.get_players()))}')

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
                    if self._player_connection_barrier.n_waiting != 0:
                        self._player_connection_barrier.reset()
                    game_db = Game.objects.get(id = self.game_id)
                    if error is None:
                        game_db.is_finished = True
                        game_db.winner_id = self.get_winner_id()
                        game_db.outcome = self.get_outcomes()
                        game_db.save(update_fields = ['is_finished', 'winner_id', 'outcome'])
                        self._logger.info(f'The game has been finished.')
                    else:
                        game_db.is_failed = True
                        game_db.error = error
                        game_db.save(update_fields = ['is_failed', 'error'])
                        for player in self.get_players():
                            player.send_error(KuhnGameLobbyStageError(error))
                        self._logger.error(f'The game has been finished with an error. Error: {error}')
                        if self._lobby_coordinator_thread != None:
                            self._lobby_coordinator_thread._stop()
                        if self._lobby_bot_thread != None:
                            self._lobby_bot_thread._stop()
                except Exception as e:
                    self._logger.error(f'Unexpected error during game finish. Error: {e}')

    def is_finished(self) -> bool:
        with self.lock:
            return self._closed.is_set()

    @staticmethod
    def resolve_kuhn_type(kuhn_type) -> int:
        try:
            return KUHN_TYPES[kuhn_type]
        except KeyError:
            raise Exception('Unknown Kuhn poker game type: {kuhn_type}')

def game_bot(lobby: KuhnGameLobby, bot_token: str, bot_exec: str, exec_delay: int):
    try: 
        lobby.get_logger().info(f'Executing bot for lobby {lobby.game_id} in {exec_delay} seconds')
        time.sleep(exec_delay)
        subprocess.run([ 'python', bot_exec, '--play', lobby.game_id, '--token', bot_token ], check = True, capture_output = True)
        lobby.get_logger().info(f'Bot in lobby {lobby.game_id} exited.')
    except Exception as e:
        lobby.finish(error = str(e))

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
                lobby.get_logger().info(f'Received message from player {message.player_id}: {message.action}')

                # First we check if the message is about to start a new round
                # It is possible for a player to send multiple 'START' actions for a single round, but they won't have any effect
                if message.action == 'START':
                    if lobby.check_players_bank():
                        lobby.start_new_round(message.player_id)
                    else:
                        lobby.finish()
                        outcome = lobby.player_outcome(message.player_id)
                        lobby.get_player(player_id = message.player_id).send_message(KuhnGameLobbyStageMessage(outcome, []))
                # If message action is not 'START' we check that the message came from a player and assume it is their next action
                elif message.player_id == current_round.player_id_turn:
                    # We register current player's action in an inner stage object
                    current_round.stage.play(message.action)

                    if current_round.stage.is_terminal():
                        # If the stage is terminal we notify both players and start a new round if both players have non-negative bank
                        for player in lobby.get_players():
                            end_round_state = f'END:{lobby.convert_evaluation(current_round.stage.evaluation(), player.player_id)}:' \
                                              f'{current_round.stage.inf_set()}'
                            player.send_message(KuhnGameLobbyStageMessage(end_round_state, ['START']))
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
                if lobby.is_finished():
                    return
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
