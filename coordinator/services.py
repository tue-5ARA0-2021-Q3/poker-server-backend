import grpc
import time
import sys
import threading
import queue
import random

from coordinator.games.kuhn_game import KuhnRootChanceGameState
from coordinator.games.kuhn_constants import CARDS_DEALINGS, NEXT
from django_grpc_framework.services import Service
from coordinator.models import Game, Player, GameTypes
from proto.game import game_pb2


def play_lobby(lobby, messages_timeout):
    lobby.wait_for_players()

    try:
        root = KuhnRootChanceGameState(CARDS_DEALINGS)
        stage = root.play(random.choice(CARDS_DEALINGS))
        cards = stage.cards

        players = lobby.get_players()
        player_id_turn = lobby.get_random_player_id()

        for player_id, player_data in players:
            if player_id == player_id_turn:
                lobby.send_message_to_player(player_id, {'state': f'{cards[0]}', 'available_actions': stage.actions})
            else:
                lobby.send_message_to_player(player_id, {'state': f'{cards[1]}', 'available_actions': ['WAIT']})

        while not lobby.is_closed() or not lobby.get_main_channel().empty():
            try:
                message = lobby.get_main_channel().get(timeout = messages_timeout)

                print(f'Received a message: {message}')

                if message['player_id'] == player_id_turn:
                    stage = stage.play(message['action'])

                    if stage.is_terminal():
                        for player_id, player_data in players:
                            try:
                                lobby.send_message_to_player(player_id, {
                                    'state': f'END:{stage.inf_set()}', 'available_actions': ['END']
                                })
                            except Exception:
                                pass
                        lobby.close()
                    else:
                        player_id_turn = lobby.get_player_opponent(player_id_turn)
                        lobby.send_message_to_player(player_id_turn, {
                            'state': stage.secret_inf_set(), 'available_actions': stage.actions
                        })
                elif message['player_id'] == lobby.get_player_opponent(player_id_turn) and \
                        (message['action'] == 'START' or message['action'] == 'WAIT'):
                    continue
                else:
                    print(f'Warn: unexpected message: {message}')
                    continue

            except queue.Empty:
                raise Exception(f'There was no message from a player for more than {messages_timeout} sec.')

    except Exception as e:
        for player_id, player_data in lobby.get_players():
            try:
                player_data['channel'].put({'error': e})
            except Exception:
                pass


class GameLobby(object):
    InitialBank = 5
    MessagesTimeout = 5

    def __init__(self, game_id):
        self.lock = threading.Lock()
        self.game_id = game_id
        self.stage = None
        self.lobby_thread = None

        # private fields
        self._closed = threading.Event()
        self._main_channel = queue.Queue()
        self._players = {}
        self._player_opponent = {}
        self._player_connection_barrier = threading.Barrier(3)

    def close(self):
        with self.lock:
            self._closed.set()

    def is_closed(self):
        with self.lock:
            return self._closed.is_set()

    def get_main_channel(self):
        return self._main_channel

    def get_players(self):
        return self._players.items()

    def get_player_opponent(self, player_id):
        return self._player_opponent[player_id]

    def get_player_channel(self, player_id):
        return self._players[player_id]['channel']

    def send_message_to_player(self, player_id, message):
        self.get_player_channel(player_id).put(message)

    def start(self):
        # First player which hits this function starts a separate thread with a game coordinator
        # Ref: play_lobby(lobby)
        with self.lock:
            if self.lobby_thread is None:
                self.lobby_thread = threading.Thread(target = play_lobby, args = (self, GameLobby.MessagesTimeout))
                self.lobby_thread.start()

    def register_player(self, player_id):
        with self.lock:
            # Check if lobby is already full or throw an exception otherwise
            if len(list(self._players.keys())) >= 2:
                raise Exception('Game lobby is full')

            # For each player we create a separate channel for messages between game coordinator and player
            self._players[player_id] = {
                'channel': queue.Queue(),
                'bank': GameLobby.InitialBank
            }

            # If both players are connected we set corresponding ids to self._player_opponent dictionary for easy lookup
            if len(self._players.keys()) == 2:
                player_ids = list(self._players.keys())
                player1_id, player2_id = player_ids[0], player_ids[1]

                self._player_opponent[player1_id] = player2_id
                self._player_opponent[player2_id] = player1_id

                # Update database entry of the game with corresponding player ids and mark it as started
                game_db = Game.objects.get(id = self.game_id)
                game_db.player_1 = player1_id
                game_db.player_2 = player2_id
                game_db.is_started = True
                game_db.save(update_fields = ['player_1', 'player_2', 'is_started'])

    def get_random_player_id(self):
        return random.choice(list(self._players.keys()))

    def wait_for_players(self):
        try:
            self._player_connection_barrier.wait(timeout = 120)
        except threading.BrokenBarrierError:
            raise Exception('Timeout waiting for another player to connect')


class GameCoordinatorService(Service):
    game_lobbies = []
    games_lock = threading.Lock()

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def Create(self, request, context):
        player = Player.objects.get(token = request.token)
        new_game = Game(created_by = player.token, game_type = GameTypes.PLAYER_PLAYER)
        instance = GameCoordinatorService.create_game_lobby_instance(new_game.id)
        if instance is not None:
            new_game.save()
            return game_pb2.CreateGameResponse(id = str(new_game.id))
        else:
            raise Exception(f'Failed to create a game instance: {new_game.id}')

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def FindOrCreate(self, request, context):
        player = Player.objects.get(token = request.token)
        game_candidates = Game.objects.filter(game_type = GameTypes.PLAYER_PLAYER, is_started = False,
                                              is_failed = False, is_finished = False)
        if len(game_candidates) == 0:
            new_game = Game(created_by = player.token, game_type = GameTypes.PLAYER_PLAYER)
            instance = GameCoordinatorService.create_game_lobby_instance(new_game.id)
            if instance is not None:
                new_game.save()
                return game_pb2.ListGameResponse(game_ids = [str(new_game.id)])
            else:
                raise Exception(f'Failed to create a game instance: {new_game.id}')
        else:
            return game_pb2.ListGameResponse(game_ids = list(map(lambda candidate: str(candidate.id), game_candidates)))

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def List(self, request, context):
        player = Player.objects.get(token = request.token)
        games = Game.objects.filter(created_by = player.token)
        return game_pb2.ListGameResponse(game_ids = list(map(lambda game: str(game.id), games)))

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def Play(self, request, context):
        metadata = dict(context.invocation_metadata())
        token = metadata['token']
        game_id = metadata['game_id']

        game_db = Game.objects.get(id = game_id)

        if game_db.is_finished:
            raise Exception('Game is finished')

        lobby = GameCoordinatorService.create_game_lobby_instance(game_id)
        lobby.start()

        lobby.register_player(token)
        lobby.wait_for_players()

        lobby_channel = lobby.get_main_channel()
        player_channel = lobby.get_player_channel(token)

        try:
            for message in request:
                if message.action != 'CONNECT' and message.action != 'WAIT':
                    lobby_channel.put({'player_id': token, 'action': message.action})
                response = player_channel.get()
                state = response['state']
                actions = response['available_actions']
                yield game_pb2.PlayGameResponse(state = state, available_actions = actions)
        except grpc.RpcError:
            pass
        except Exception as e:
            print('Unhandled exception: ', e)
            print(sys.exc_info())
        finally:
            GameCoordinatorService.remove_game_lobby_instance(game_id)

        # # time.sleep(1.0)

        # if instance.is_opponent_waiting(token):
        #     instance.notify_opponent(token)

        # # Game.objects.update(id = game_id, is_finished = True)
        # if instance.is_primary_player(token):
        #     with GameCoordinatorService.games_lock:
        #         try:
        #             instance.finish_game()
        #             game_db = Game.objects.get(id = game_id)
        #             game_db.is_finished = True
        #             game_db.winner_id = instance.get_winner_id()
        #             game_db.outcome = instance.get_outcomes()
        #             game_db.save(update_fields = [ 'is_finished', 'winner_id', 'outcome' ])
        #             GameCoordinatorService.games.remove(instance)
        #         except:
        #             print("Unexpected error:", sys.exc_info()[ 0 ])
        #             return

    @staticmethod
    def create_game_lobby_instance(game_id):
        lobby = None
        with GameCoordinatorService.games_lock:
            game_lobbies = list(filter(lambda game: game.game_id == game_id, GameCoordinatorService.game_lobbies))
            if len(game_lobbies) == 0:
                lobby = GameLobby(game_id)
                GameCoordinatorService.game_lobbies.append(lobby)
            else:
                lobby = game_lobbies[0]
        return lobby

    @staticmethod
    def get_game_lobby_instance(game_id):
        lobby = None
        with GameCoordinatorService.games_lock:
            game_lobbies = list(filter(lambda game: game.game_id == game_id, GameCoordinatorService.game_lobbies))
            if len(game_lobbies) == 0:
                raise Exception(f'There is no game lobby instance with id: {game_id}')
            else:
                lobby = game_lobbies[0]
        return lobby

    @staticmethod
    def remove_game_lobby_instance(game_id):
        with GameCoordinatorService.games_lock:
            game_lobbies = list(filter(lambda game: game.game_id == game_id, GameCoordinatorService.game_lobbies))
            for lobby in game_lobbies:
                GameCoordinatorService.game_lobbies.remove(lobby)
