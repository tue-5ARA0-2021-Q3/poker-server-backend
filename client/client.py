import grpc
import time
import random
import collections
import threading

from proto.game import game_pb2
from proto.game import game_pb2_grpc

def getlist(token=None):
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
        return stub.List(game_pb2.ListGameRequest(token=token))

def create(token=None):
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
        return stub.Create(game_pb2.CreateGameRequest(token=token))


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

  def make_request(self, request):
    self.add_request(request)
    with self.response_condition:
      while True:
        self.response_condition.wait()
        if request in self.responses:
          return self.responses[request.id]

def play(token=None, gameid=None):
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
        player_client = PlayerClient()
        player_client.add_request(game_pb2.PlayGameRequest(id = 1, token=token, action='move'))
        count = 1
        for response in stub.Play(player_client):
            # print(response)
            player_client.add_response(response)
            if response.action == 'end':
                break
            else:
                count = count + 1
                player_client.add_request(game_pb2.PlayGameRequest(id = count, token=token, action='move'))
        return player_client.responses