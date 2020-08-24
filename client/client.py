import grpc

from proto.game import game_pb2
from proto.game import game_pb2_grpc

def foo():
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
        print(stub.Create(game_pb2.CreateGameRequest(token='411792fd-a4a3-4888-846f-a466160af468')))