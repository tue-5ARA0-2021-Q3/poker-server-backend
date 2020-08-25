import grpc

from django_grpc_framework.services import Service
from coordinator.models import Game, Player, GameTypes
from proto.game import game_pb2

class GameCoordinatorService(Service):

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
        count = 3
        for message in request:
            if count == 0:
                yield game_pb2.PlayGameResponse(id = message.id, action = 'end')
                break
            count  = count - 1
            # print(request)
            # player = Player.objects.get(token = request.token)
            yield game_pb2.PlayGameResponse(id = message.id, action = 'continue')
