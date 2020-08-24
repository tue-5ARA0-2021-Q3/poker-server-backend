import grpc

from django_grpc_framework.services import Service
from coordinator.models import Game, UserToken
from proto.game import game_pb2

class GameCoorinatorService(Service):

    def Create(self, request, context):
        userToken = UserToken.objects.get(token = request.token)
        newgame = Game(created_by = userToken.token)
        newgame.save()
        return game_pb2.CreateGameResponse(id = str(newgame.id))
