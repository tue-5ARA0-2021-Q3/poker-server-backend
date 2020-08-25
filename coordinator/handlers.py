from coordinator.services import GameCoordinatorService
from proto.game import game_pb2_grpc

def game_coordinator_handlers(server):
    game_pb2_grpc.add_GameCoordinatorControllerServicer_to_server(GameCoordinatorService.as_servicer(), server)