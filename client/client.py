import grpc
import time
import random
import collections
import threading

from proto.game import game_pb2
from proto.game import game_pb2_grpc

class PlayerClient(object):
  def __init__(self):
    self.stop_event         = threading.Event()
    self.request_condition  = threading.Condition()
    self.response_condition = threading.Condition()
    self.requests           = collections.deque()
    self.last_request       = None
    self.expected_responses = collections.deque()
    self.responses = {}

  def _next(self):
    with self.request_condition:
      while not self.requests and not self.stop_event.is_set():
        self.request_condition.wait()
      if len(self.requests) > 0:
        return self.requests.popleft()
      else:
        raise StopIteration()

  def next(self):
    return self._next()

  def __next__(self):
    return self._next()

  def add_response(self, response):
    with self.response_condition:
      request = self.expected_responses.popleft()
      self.responses[request.id] = response
      self.response_condition.notify_all()

  def add_request(self, request):
    with self.request_condition:
      self.requests.append(request)
      with self.response_condition:
        self.expected_responses.append(request)
      self.request_condition.notify()

  def close(self):
    self.stop_event.set()
    with self.request_condition:
      self.request_condition.notify()

class GameState(object):

    def __init__(self):
        self._history = []

    def save_action_in_history(self, action):
        return self._history.append(action)

    def history(self):
        return self._history

    def available_actions(self):
        return [ 'continue', 'end' ]

class Client(object):

    def __init__(self, token=None):
        if token is None:
            raise Exception('Empty token has been provided')
        self.token = token

    def getlist(self):
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
            stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
            player_client = PlayerClient()
            game_state    = GameState()

            initial_action = 'continue'
            
            player_client.add_request(game_pb2.PlayGameRequest(id = 1, token=self.token, action=initial_action))

            count = 1
            for response in stub.Play(player_client):
                print('Response from server: ', count, response.action)
                player_client.add_response(response)
                game_state.save_action_in_history(response.action)
                if response.action == 'end':
                    break
                else:
                    count = count + 1
                    next_action = agent.make_action(game_state)
                    player_client.add_request(game_pb2.PlayGameRequest(id = count, token=self.token, action=next_action))
            
            agent.end(game_state)
            player_client.close()
            return player_client.responses