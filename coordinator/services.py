import grpc
import time
import threading

from coordinator.games.kuhn_poker import KuhnPokerGameInstance
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
            if action == 'connection':
                yield game_pb2.PlayGameResponse(action = 'connected')

            time.sleep(0.1)

            if action == 'continue':
                if instance.is_primary_player(token):
                    # do somethinf
                    yield game_pb2.PlayGameResponse(action = str(action))
                    instance.notify_opponent(token)
                    instance.wait_for_opponent(token)
                elif instance.is_secondary_player(token):
                    # do something here
                    instance.wait_for_opponent(token)
                    yield game_pb2.PlayGameResponse(action = str(action))
                    instance.notify_opponent(token)
                else:
                    raise Exception(f'Unknown player with token { token }')

            if action == 'end':
                break

        instance.finish_game()
            
