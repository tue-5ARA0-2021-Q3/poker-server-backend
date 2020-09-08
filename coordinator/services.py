import grpc
import time
import threading

from coordinator.games.kuhn_poker import KuhnPokerGameInstance
from coordinator.games.kuhn_game import KuhnRootChanceGameState
from coordinator.games.kuhn_constants import CARDS_DEALINGS
from django_grpc_framework.services import Service
from coordinator.models import Game, Player, GameTypes
from proto.game import game_pb2


class GameCoordinatorService(Service):
    games      = []
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

        game_db = Game.objects.get(id = gameid)
        
        if game_db.is_finished:
            raise Exception('Game is finished')

        with GameCoordinatorService.games_lock:
            game_instances = list(filter(lambda game: game.gameid == gameid, GameCoordinatorService.games))
            if len(game_instances) == 0:
                instance = KuhnPokerGameInstance(gameid)
                GameCoordinatorService.games.append(instance)
            else:
                instance = game_instances[0]

    
        instance.register_player(token)
        instance.wait_for_all_players()

        for message in request:
            # Some code for actions
            action = message.action

            if action == 'start':
                if instance.is_primary_player(token):
                    instance.root  = KuhnRootChanceGameState(CARDS_DEALINGS)
                    instance.stage = instance.root
                    instance.stage = instance.stage.play(CARDS_DEALINGS[1])
                    yield game_pb2.PlayGameResponse(action = 'continue', available_actions = instance.stage.actions)
                elif instance.is_secondary_player(token):
                    instance.wait_for_opponent(token)
                    yield game_pb2.PlayGameResponse(action = 'continue', available_actions = instance.stage.actions)
            elif action == 'end':
                break
            else:
                instance.stage = instance.stage.play(action)
                instance.notify_opponent(token)
                instance.wait_for_opponent(token)
                if not instance.stage.is_terminal():
                    yield game_pb2.PlayGameResponse(action = 'continue', available_actions = instance.stage.actions)
                else:
                    yield game_pb2.PlayGameResponse(action = 'continue', available_actions = [ 'end' ])
                    instance.notify_opponent(token)

        # time.sleep(1.0)

        if instance.is_opponent_waiting(token):
            instance.notify_opponent(token)
            
        # Game.objects.update(id = gameid, is_finished = True)
        instance.finish_game()

        with GameCoordinatorService.games_lock:
            try:
                GameCoordinatorService.games.remove(instance)
            except:
                return
