import grpc

from client.state import ClientGameState
from client.events import ClientRequestEventsIterator

from proto.game import game_pb2
from proto.game import game_pb2_grpc


class Client(object):

    def __init__(self, token = None):
        if token is None:
            raise Exception('Empty token has been provided')
        self.token = token

    def get_list(self):
        with grpc.insecure_channel('localhost:50051') as channel:
            stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
            return stub.List(game_pb2.ListGameRequest(token = self.token))

    def create(self):
        with grpc.insecure_channel('localhost:50051') as channel:
            stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
            return stub.Create(game_pb2.CreateGameRequest(token = self.token))

    def play(self, game_id = None, agent = None):
        if game_id is None:
            raise Exception('Empty game_id has been provided')
        if agent is None:
            raise Exception('Empty agent has been provided')

        with grpc.insecure_channel('localhost:50051') as channel:
            stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
            requests = ClientRequestEventsIterator()

            if game_id == 'random':
                request_random_game = stub.FindOrCreate(game_pb2.CreateGameRequest(token = self.token))
                game_candidates = list(request_random_game.game_ids)
                if len(game_candidates) == 0:
                    raise Exception('It is not possible to start a random game')
                game_id = game_candidates[0]

            metadata = [
                ('token', str(self.token)),
                ('game_id', str(game_id))
            ]

            state = ClientGameState(str(game_id), str(self.token), 5)
            state.start_new_round()

            agent.on_new_round_request(state)

            requests.set_initial_request(game_pb2.PlayGameRequest(action = 'CONNECT'))

            for response in stub.Play(requests, metadata = metadata):

                if response.state.startswith('CARD'):
                    _, order, card = response.state.split(':')
                    state.get_last_round_state().set_turn_order(order)
                    state.get_last_round_state().set_card(card)

                if response.available_actions != ['WAIT']:
                    state.get_last_round_state().set_available_actions(response.available_actions)
                    if response.state.startswith('DEFEAT') or response.state.startswith('WIN'):
                        agent.end(state, response.state)
                        break
                    elif response.state.startswith('ERROR'):
                        agent.on_error(response.state)
                        break
                    elif response.state.startswith('END'):
                        _, outcome, result = response.state.split(':')
                        _, cards, *last = result.split('.')
                        state.get_last_round_state().add_move_history('.'.join(last))
                        state.get_last_round_state().set_outcome(outcome)
                        state.get_last_round_state().set_result(result)
                        state.get_last_round_state().set_cards(cards)
                        state.update_bank(outcome)
                        agent.on_round_end(state, state.get_last_round_state())
                        state.start_new_round()
                        agent.on_new_round_request(state)
                        requests.make_request(game_pb2.PlayGameRequest(action = 'START'))
                    else:
                        if not response.state.startswith('CARD'):
                            state.get_last_round_state().add_move_history(response.state)
                        next_action = agent.make_action(state, state.get_last_round_state())
                        if response.state.startswith('CARD'):
                            state.get_last_round_state().add_move_history(f'{next_action}')
                        else:
                            state.get_last_round_state().add_move_history(f'{response.state}.{next_action}')
                        requests.make_request(game_pb2.PlayGameRequest(action = next_action))
                else:
                    requests.make_request(game_pb2.PlayGameRequest(action = 'WAIT'))

            requests.make_request(game_pb2.PlayGameRequest(action = 'END'))

            requests.close()
            return state
