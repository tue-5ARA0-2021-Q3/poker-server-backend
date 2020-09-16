import grpc
import time
import random
import collections
import threading
import sys

from client.state import GameState
from client.events import ClientRequestEventsIterator

from proto.game import game_pb2
from proto.game import game_pb2_grpc

class Client(object):

    def __init__(self, token=None):
        if token is None:
            raise Exception('Empty token has been provided')
        self.token = token

    def get_list(self):
        with grpc.insecure_channel('localhost:50051') as channel:
            stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
            return stub.List(game_pb2.ListGameRequest(token=self.token))

    def create(self):
        with grpc.insecure_channel('localhost:50051') as channel:
            stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
            return stub.Create(game_pb2.CreateGameRequest(token=self.token))

    def play(self, gameid=None, agent=None):
        if gameid is None:
            raise Exception('Empty gameid has been provided')
        if agent is None:
            raise Exception('Empty agent has been provided')

        with grpc.insecure_channel('localhost:50051') as channel:
          stub      = game_pb2_grpc.GameCoordinatorControllerStub(channel)
          requests  = ClientRequestEventsIterator()
          state     = GameState()
          metadata  = [ 
            ('token', str(self.token)), 
            ('gameid', str(gameid))
          ]
          
          requests.set_initial_request(game_pb2.PlayGameRequest(action = 'START'))

          for response in stub.Play(requests, metadata=metadata):
              state.save_action_in_history(response.state)
              state.set_available_actions(response.available_actions)
              if response.state.startswith('END'):
                  break
              else:
                  next_action = agent.make_action(state)
                  requests.make_request(game_pb2.PlayGameRequest(action = next_action))

          requests.make_request(game_pb2.PlayGameRequest(action = 'END'))
          
          agent.end(state)
          requests.close()
          return state.history()
            
            