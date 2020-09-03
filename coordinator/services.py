import grpc
import time
import threading

from django_grpc_framework.services import Service
from coordinator.models import Game, Player, GameTypes
from proto.game import game_pb2

class GameStep(object):
    def __init__(self, playerid, action):
        self.playerid = playerid
        self.action = action

class GameInstance(object):

    def __init__(self, gameid):
        self.gameid            = gameid
        self.player1           = None
        self.player2           = None
        self.current_player    = None
        self.player1_condition = threading.Condition()
        self.player2_condition = threading.Condition()
        self.player1_connected = threading.Event()
        self.player2_connected = threading.Event()
        self.game_over_event   = threading.Event()
        self.history           = []

    def get_gameid(self):
        return self.gameid

    def register_player(self, token):
        self.__check_game_is_on()
        
        if self.player1 is None:
            self.player1 = token
            self.current_player = token
            self.player1_connected.set()
        elif self.player2 is None:
            self.player2 = token
            self.player2_connected.set()
        else:
            raise Exception('More than two players for a game instance')

    def wait_for_connection(self):
        self.__check_game_is_on()

        self.player1_connected.wait()
        self.player2_connected.wait()

    def wait_for_opponent(self, token):
        self.__check_game_is_on()

        if self.current_player != token:
            if self.player1 == token:
                with self.player1_condition:
                    self.player1_condition.wait()
            elif self.player2 == token:
                with self.player2_condition:
                    self.player2_condition.wait()
            else:
                raise Exception('Invalid token provided in \'wait_for_opponent()\' method.')

    def get_opponent_last_action(self, token):
        self.__check_game_is_on()

        opponent_actions = list(filter(lambda x: x.playerid != token, self.history))
        return opponent_actions[-1]

    def save_action_and_notify_opponent(self, token, action):
        self.__check_game_is_on()

        if self.current_player != token:
            raise Exception('Invalid player order')
        
        self.history.append(GameStep(token, action))

        if self.player1 == token:
            with self.player2_condition:
                self.current_player = self.player2
                self.player2_condition.notify_all()
        elif self.player2 == token:
            with self.player1_condition:
                self.current_player = self.player1
                self.player1_condition.notify_all()    

    def finish_game(self):
        self.game_over_event.set()

    def __check_game_is_on(self):
        if self.game_over_event.is_set():
            raise Exception('Game is over')


class GameCoordinatorService(Service):
    games = []
    games_lock = threading.Lock()

    def Create(self, request, context):
        player = Player.objects.get(token = request.token)
        newgame = Game(created_by = player.token, game_type = GameTypes.PLAYER_PLAYER)
        newgame.save()
        return game_pb2.CreateGameResponse(id = str(newgame.id))

    def List(self, request, context):
        player = Player.objects.get(token = request.token)
        games = Game.objects.filter(created_by = player.token)
        return game_pb2.ListGameResponse(game_ids = list(map(lambda game: str(game.id), games)))

    def Play(self, request, context):
        metadata = dict(context.invocation_metadata())
        token  = metadata['token']
        gameid = metadata['gameid']

        with GameCoordinatorService.games_lock:
            game_instances = list(filter(lambda game: game.get_gameid() == gameid, GameCoordinatorService.games))
            if len(game_instances) == 0:
                instance = GameInstance(gameid)
                GameCoordinatorService.games.append(instance)
            else:
                instance = game_instances[0]

        print('Player ' + str(token) + ' connected for game: ' + str(gameid))

        print('Before Player1: ' + str(instance.player1))
        print('Before Player2: ' + str(instance.player2))

        instance.register_player(token)

        print('After Player1: ' + str(instance.player1))
        print('After Player2: ' + str(instance.player2))

        instance.wait_for_connection()

        print('Both players are connected to the game: ' + str(gameid))
        print('Current player is ' + str(instance.current_player))

        instance.wait_for_opponent(token)

        print('Player ' + str(token) + ' in the game')

        for message in request:
            # Some code for actions
            action = message.action

            print('Player ' + str(token) + 'made a move and notifies opponent')

            instance.save_action_and_notify_opponent(token, action)

            print('Player ' + str(token) + 'waits for an opponent\'s move')

            instance.wait_for_opponent(token)
            time.sleep(0.2)
            # opponent_action = instance.get_last_opponent_action()
            yield game_pb2.PlayGameResponse(id = message.id, action = str(action))

        instance.finish_game()
            
