import threading
import queue
import random
import logging
import time
import traceback

from typing import List
from django.conf import settings

from coordinator.kuhn.kuhn_poker import KuhnRootChanceGameState
from coordinator.kuhn.kuhn_constants import CARDS_DEALINGS, POSSIBLE_CARDS, CoordinatorActions, KuhnCoordinatorMessage, KuhnCoordinatorEventTypes
from coordinator.kuhn.kuhn_player import KuhnGameLobbyPlayer
from coordinator.models import Game

class KuhnGame(object):
    InitialBank     = settings.KUHN_GAME_INITIAL_BANK
    MessagesTimeout = settings.COORDINATOR_WAITING_TIMEOUT

    def __init__(self, coordinator, player1: KuhnGameLobbyPlayer, player2: KuhnGameLobbyPlayer, game_type: int, channel: queue.Queue):

        dbgame = Game(
            created_by_id = coordinator.id,
            player1_id = player1.player_token,
            player2_id = player2.player_token,
            game_type  = game_type
        )
        dbgame.save()

        self.id            = str(dbgame.id)
        self.lock          = threading.RLock()
        self.coordinator   = coordinator
        self.rounds        = []
        self.player1       = player1
        self.player2       = player2
        self.game_type     = game_type
        self.error         = None
        self.finished      = threading.Event()
        self.channel       = channel
        self.logger        = logging.getLogger('kuhn.game')

    def play(self):
        try:
            self.logger.debug(f'Kuhn game { self.id } initiated `play` procedure.')
            
            # First both players receive an instruction to start a new game
            for player in self.get_players():
                player.send_message(KuhnCoordinatorMessage(KuhnCoordinatorEventTypes.GameStart))

            # Server creates a new round, but both player must send a `ROUND` action first to accept the invitation
            current_round = self.create_new_round()

            # We run an inner cycle until lobby is closed or to process last messages after lobby has been closed
            while not self.is_finished() or not self.channel.empty():
                try:
                    # Game coordinator waits for a message from any player
                    message = self.channel.get(timeout = KuhnGame.MessagesTimeout)

                    self.logger.info(f'Received message from player { message.player_id }: { message.action }')

                    # First we check if the message is about to start a new round
                    # It is possible for a player to send multiple 'START' actions for a single round, but they won't have any effect
                    if message.action == CoordinatorActions.NewRound:
                        if self.check_players_bank():
                            self.start_new_round(message.player_id)
                        else:
                            self.finish()
                            self.get_player(message.player_id).send_message(KuhnCoordinatorMessage(
                                KuhnCoordinatorEventTypes.GameResult, 
                                game_result = self.player_outcome(message.player_id)
                            ))
                    # Second we chand if player requests a list of available actions for him
                    # That usually happens right after card deal event
                    elif message.action == CoordinatorActions.AvailableActions:
                        player = self.get_player(message.player_id)
                        if player.player_token == current_round.player_id_turn:
                            player.send_message(KuhnCoordinatorMessage(
                                KuhnCoordinatorEventTypes.NextAction, 
                                inf_set = current_round.stage.public_inf_set(), 
                                actions = current_round.stage.actions()
                            ))
                        else:
                            player.send_message(KuhnCoordinatorMessage(
                                KuhnCoordinatorEventTypes.NextAction, 
                                inf_set = current_round.stage.public_inf_set(), 
                                actions = [ CoordinatorActions.Wait ]
                            ))
                    # Wait is an utility message
                    elif message.action == CoordinatorActions.Wait:
                        continue
                    # If message action is not 'START' we check that the message came from a player and assume it is their next action
                    elif message.player_id == current_round.player_id_turn:
                        # We register current player's action in an inner stage object
                        
                        current_round.stage.play(message.action)

                        if current_round.stage.is_terminal():
                            # If the stage is terminal we notify both players and we always start a new round even if ssome player has a negative bank
                            # However we always check players banks in the beginning of each round
                            for player in self.get_players():
                                player.send_message(KuhnCoordinatorMessage(
                                    KuhnCoordinatorEventTypes.RoundResult, 
                                    evaluation = self.convert_evaluation(current_round.stage.evaluation(), player.player_token), 
                                    inf_set    = current_round.stage.inf_set()
                                ))
                            self.evaluate_round()
                            current_round = self.create_new_round()
                        else:
                            # If the stage is not terminal we swap current's player id and wait for a new action of second player
                            current_round.player_id_turn = self.get_player_opponent(current_round.player_id_turn).player_token
                            self.get_player(current_round.player_id_turn).send_message(KuhnCoordinatorMessage(
                                KuhnCoordinatorEventTypes.NextAction,
                                inf_set = current_round.stage.public_inf_set(), 
                                actions = current_round.stage.actions()
                            ))
                    else:
                        print(f'Warn: unexpected message from player_id = { message.player_id }: [ action = {message.action} ]')
                        continue

                except queue.Empty:
                    if self.is_finished():
                        return
                    raise Exception(f'There was no message from player for more than { KuhnGame.MessagesTimeout } sec.')

        except Exception as e:
            traceback.print_exc()
            self.finish(error = str(e))

    def is_finished(self):
        with self.lock:
            return self.finished.is_set()

    def finish(self, error = None):
        with self.lock:
            if not self.is_finished():
                is_failed, error = (False, None) if error is None else (True, str(error))
                if is_failed:
                    self.logger.warning(f'Kuhn game { self.id } finished with an error: { error }')
                self.error = error
                Game.objects.filter(id = self.id).update(
                    is_finished = True, 
                    is_failed   = is_failed, 
                    winner      = self.get_winner_token(),
                    outcome     = self.get_outcome(),
                    error       = error
                )
                self.finished.set()

    def get_players(self) -> List[KuhnGameLobbyPlayer]:
        return [ self.player1, self.player2 ]

    def get_player(self, player_token: str) -> KuhnGameLobbyPlayer:
        with self.lock:
            if player_token == self.player1.player_token:
                return self.player1
            elif player_token == self.player2.player_token:
                return self.player2
            return None

    def get_player_opponent(self, player_token: str) -> KuhnGameLobbyPlayer:
        with self.lock:
            if player_token == self.player1.player_token:
                return self.player2
            elif player_token == self.player2.player_token:
                return self.player1
            return None

    def get_random_player(self) -> str:
        with self.lock:
            return random.choice(self.get_players())

    def get_winner_token(self) -> str:
        with self.lock:
            for player in self.get_players():
                if player.bank <= 0:
                    return self.get_player_opponent(player.player_token).player_token
            return None

    def get_outcome(self) -> str:
        return '|'.join(list(map(lambda _round: f'{_round.stage.inf_set()}:{_round.evaluation}', self.rounds[0:-1])))

    def get_valid_card_ranks(self):
        return POSSIBLE_CARDS[self.game_type]

    def get_card_dealings(self):
        return CARDS_DEALINGS[self.game_type]

    def get_last_round(self):
        return self.rounds[-1] if len(self.rounds) >= 1 else None

    def check_players_bank(self):
        with self.lock:
        # Check if lobby can create a new round
        # True if both players have enough bank
        # False otherwise
            for player in self.get_players():
                if player.bank <= 0:
                    return False
            return True

    def player_outcome(self, player_token):
        with self.lock:
            player = self.get_player(player_token)
            if player.bank <= 0:
                return 'DEFEAT'
            else:
                return 'WIN'

    def create_new_round(self):
        with self.lock:
            last_round = self.get_last_round()
            # Check if there was a round already and check if it was terminated
            # Throw an error instead, in reality this error should never be raised since game coordinator
            # creates a new round only on termination
            if last_round is None or last_round.stage.is_terminal():
                _first_player = self.get_player_opponent(last_round.first_player) if last_round is not None else self.get_random_player()
                _round        = KuhnGameRound(first_player = _first_player.player_token, card_dealings = self.get_card_dealings())
                self.rounds.append(_round)
                self.logger.info(f'A new round has been created. First player is { _first_player.player_token }')
                return _round
            else:
                self._logger.error('It is not allowed to start a new round while previous one is not completed')
                raise Exception('It is not allowed to start a new round while previous one is not completed')

    def start_new_round(self, player_token):
        with self.lock:
            # This function starts a new round for each player
            # If player repeatedly sends 'START' messages this function won't do anything until a new round is created
            last_round = self.get_last_round()

            # Check if player already started this round and exit if it is true
            if player_token in last_round.started and last_round.started[player_token] is True:
                return

            player = self.get_player(player_token)
            last_round.started[player_token] = True

            self.logger.info(f'Player { player_token } accepted new round')

            # First player (last_round.player_id_turn) starts the round
            # Both players later on request a list of their available actions
            if player.player_token == last_round.player_id_turn:
                player.send_message(KuhnCoordinatorMessage(
                    KuhnCoordinatorEventTypes.CardDeal, 
                    card       = last_round.stage.card(0), 
                    turn_order = 1, 
                    actions    = [ CoordinatorActions.AvailableActions ]
                ))
            else:
                player.send_message(KuhnCoordinatorMessage(
                    KuhnCoordinatorEventTypes.CardDeal, 
                    card       = last_round.stage.card(1), 
                    turn_order = 2, 
                    actions    = [ CoordinatorActions.AvailableActions ]
                ))

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
                if last_round.first_player == player.player_token:
                    player.bank = player.bank + evaluation
                else:
                    player.bank = player.bank - evaluation

            last_round.evaluation = evaluation
            last_round.is_evaluated = True

            self.logger.info(f'Round has been evaluated. Banks: { list(map(lambda p: p.bank, self.get_players())) }')

    def convert_evaluation(self, evaluation, player_token):
        with self.lock:
            last_round = self.get_last_round()
            if last_round.first_player == player_token:
                return evaluation
            else:
                return -evaluation



# `KuhnGameLobbyStage` is a game logic wrapper, see also `kuhn_game.py`
class KuhnGameLobbyStage(object):

    def __init__(self, card_dealings):
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

    def public_inf_set(self):
        return self._stage.public_inf_set()

    def evaluation(self):
        return self._stage.evaluation()


# `KuhnGameRound` is a single round logic wrapper, see also `kuhn_game.py` and `KuhnGameLobbyStage`
class KuhnGameRound(object):

    def __init__(self, first_player, card_dealings):
        self.stage          = KuhnGameLobbyStage(card_dealings)
        self.started        = {}
        self.evaluation     = 0
        self.is_evaluated   = False
        self.first_player   = first_player
        self.player_id_turn = self.first_player


# TODO remove
# class KuhnGameLobby(object):
#     InitialBank = settings.KUHN_GAME_INITIAL_BANK
#     MessagesTimeout = settings.COORDINATOR_WAITING_TIMEOUT
#     LobbyBots = []

#     def __init__(self, game_id: str, kuhn_type: int, player_type: int):
#         self.lock = threading.Lock()
#         self.game_id = game_id
#         self.rounds = []
#         self.channel = queue.Queue()
#         self.kuhn_type = kuhn_type
#         self.player_type = player_type

#         if player_type == PlayerTypes.PLAYER_BOT and not settings.ALLOW_BOTS:
#             raise Exception('Playing with bots is disallowed in server settings')

#         # private fields
#         self._closed = threading.Event()
#         self._lobby_coordinator_thread = None
#         self._lobby_bot_thread = None
#         self._player_connection_barrier = threading.Barrier(3)

#         self._players = {}
#         self._player_opponent = {}
#         self._logger = GameActionsLogger(game_id)

#     def get_players(self) -> List[KuhnGameLobbyPlayer]:
#         return list(self._players.values())

#     def get_player(self, player_id: str) -> KuhnGameLobbyPlayer:
#         return self._players[player_id]

#     def get_player_ids(self) -> List[str]:
#         return list(self._players.keys())

#     def get_num_players(self) -> int:
#         return len(self.get_player_ids())

#     def get_player_opponent(self, player_id: str) -> str:
#         return self._player_opponent[player_id]

#     def get_player_channel(self, player_id: str) -> queue.Queue:
#         return self._players[player_id].channel

#     def get_random_player_id(self) -> str:
#         return random.choice(list(self._players.keys()))

#     def get_winner_id(self) -> str:
#         for player in self.get_players():
#             if player.bank <= 0:
#                 return self.get_player_opponent(player.player_id)
#         return ''

#     def get_outcomes(self) -> str:
#         return '|'.join(list(map(lambda _round: f'{_round.stage.inf_set()}:{_round.evaluation}', self.rounds[0:-1])))

#     def get_logger(self):
#         return self._logger

#     def get_valid_card_ranks(self):
#         return POSSIBLE_CARDS[self.kuhn_type]

#     def get_card_dealings(self):
#         return CARDS_DEALINGS[self.kuhn_type]

#     def get_last_round(self):
#         return self.rounds[-1] if len(self.rounds) >= 1 else None

    

#     def check_players_bank(self):
#         # Check if lobby can create a new round
#         # True if both players have enough bank
#         # False otherwise
#         can_continue = True
#         for player in self.get_players():
#             if player.bank <= 0:
#                 can_continue = False
#         return can_continue

#     def player_outcome(self, player_id):
#         player = self.get_player(player_id)
#         if player.bank <= 0:
#             return 'DEFEAT'
#         else:
#             return 'WIN'

#     def finish(self, error = None):
#         if not self.is_finished():
#             with self.lock:
#                 self._closed.set()
#                 try:
#                     if self._player_connection_barrier.n_waiting != 0:
#                         self._player_connection_barrier.reset()
#                     game_db = Game.objects.get(id = self.game_id)
#                     if error is None:
#                         game_db.is_finished = True
#                         game_db.winner_id = self.get_winner_id()
#                         game_db.outcome = self.get_outcomes()
#                         game_db.save(update_fields = ['is_finished', 'winner_id', 'outcome'])
#                         self._logger.info(f'The game has been finished.')
#                     else:
#                         game_db.is_failed = True
#                         game_db.error = str(error)
#                         game_db.save(update_fields = ['is_failed', 'error'])
#                         for player in self.get_players():
#                             player.send_message(KuhnGameLobbyMessage(KuhnGameLobbyEvents.Error, error = str(error)))
#                         self._logger.error(f'The game has been finished with an error. Error: {error}')
#                         if self._lobby_coordinator_thread != None:
#                             self._lobby_coordinator_thread._stop()
#                         if self._lobby_bot_thread != None:
#                             self._lobby_bot_thread._stop()
#                 except Exception as e:
#                     self._logger.error(f'Unexpected error during game finish. Error: {e}')

#     def is_finished(self) -> bool:
#         with self.lock:
#             return self._closed.is_set()



# def game_lobby_coordinator(lobby: KuhnGameLobby, messages_timeout: int):
#     try:
#         # In the beginning of the session lobby waits for both players to be connected
#         # Throws an error if second player did not connect in some reasonable amount of time (check wait_for_players() function)
#         lobby.wait_for_players()

        

#     except Exception as e:
#         for player in lobby.get_players():
#             # noinspection PyBroadException
#             try:
#                 lobby.get_logger().error(f'Unknown exception: { e }')
#                 player.send_message(KuhnGameLobbyMessage(
#                     KuhnGameLobbyEvents.Error,
#                     error = str(e)
#                 ))
#             except Exception:
#                 pass
#         lobby.finish(error = str(e))
#     finally:
#         lobby.finish()
