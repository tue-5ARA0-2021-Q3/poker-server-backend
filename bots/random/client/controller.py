import random
import grpc

from client.state import ClientGameState
from client.events import ClientRequestEventsIterator
from math import sqrt
from PIL import Image
from proto.game import game_pb2
from proto.game import game_pb2_grpc
from enum import Enum
class ControllerActions(str, Enum):
    Connect = 'CONNECT'
    NewRound = 'ROUND'
    AvailableActions = 'AVAILABLE_ACTIONS'
    Wait = 'WAIT'
    IsAlive = 'IS_ALIVE',
    ConfirmEndGame = 'CONFIRM_END_GAME'

class Controller(object):

    def __init__(self, token = None, server_address = None):
        if token is None:
            raise Exception('Empty token has been provided')
        if server_address is None:
            raise Exception('Empty token has been provided')
        self.token = token
        self.server_address = server_address

    def rename(self, new_name):
        with grpc.insecure_channel(self.server_address) as channel:
            stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
            return stub.Rename(game_pb2.PlayerRenameRequest(token = self.token, name = new_name))

    def create(self, game_type):
        with grpc.insecure_channel(self.server_address) as channel:
            stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
            return stub.Create(game_pb2.CreateGameRequest(token = self.token, game_type = game_type))

    def play(self, coordinator_id = None, game_type = None, agent_cb = None):
        try:
            if coordinator_id is None:
                raise Exception('Empty coordinator id has been provided')
            if game_type is None:
                raise Exception('Empty game type has been provided')
            if agent_cb is None:
                raise Exception('Empty agent has been provided')

            agent          = None
            is_finalized   = True

            with grpc.insecure_channel(self.server_address) as channel:
                stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
                requests = ClientRequestEventsIterator()

                metadata = [
                    ('token', str(self.token)),
                    ('coordinator_id', str(coordinator_id)),
                    ('game_type', str(game_type))
                ]

                state = ClientGameState(str(coordinator_id), str(self.token), 5)

                requests.set_initial_request(game_pb2.PlayGameRequest(action = ControllerActions.Connect))
                
                for response in stub.Play(requests, metadata = metadata):
                    # We do not expect to receive the `Nothing` event from a server
                    # That would indicate something is broken
                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.Nothing:
                        raise Exception('Broken response from server')

                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.Error:
                        if agent is not None:
                            agent.on_error(response.error)
                        print(f'Error: { response.error }')
                        break

                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.UpdateCoordinatorId:
                        print(f'Coordinator ID has been updated by the server: { response.coordinator_id }. Report this ID to your teacher in case of any problems with the game.\n')
                        state._coordinator_id = response.coordinator_id # we use private field here
                        continue

                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.GameStart:
                        if not is_finalized:
                            raise Exception('Cannot create new agent when old one is not yet finalized.')
                        agent = agent_cb()
                        agent.on_game_start()
                        state.start_new_round()
                        agent.on_new_round_request(state)
                        requests.make_request(game_pb2.PlayGameRequest(action = ControllerActions.NewRound))
                        continue

                    # In case of the `CardDeal` we receive a `turn_order` and optionally a `card_rank` (if enabled in server settings)
                    # We also receive a byte image of a card, we convert it before saving it in the state
                    # This branch also calls agent's `on_image` method.
                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.CardDeal:
                        order = response.turn_order
                        card  = response.card_rank

                        state.get_last_round_state().set_turn_order(order)
                        state.get_last_round_state().set_card(card)

                        card_image = response.card_image
                        if card_image is not None:
                            image_size = int(sqrt(len(card_image)))
                            image = Image.frombytes('L', (image_size, image_size), card_image)
                            state.get_last_round_state().set_card_image(image)
                            agent.on_image(image)

                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.Close:
                        break

                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.InvalidAction:
                        print('Server sent invalid action event. Force finishing the game.')

                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.OpponentInvalidAction:
                        print('Server sent invalid action event from the opponent. Force finishing the game.')

                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.OpponentDisconnected:
                        print('Server sent disconnected event from the opponent. Force finishing the game.')

                    # In case if only one action is available controller automatically invokes this action
                    # This might be a simple `WAIT` event or maybe `IS_ALIVE` ping to ensure player is still connected
                    # In any case controller normally closes connection only on `Close` event
                    if len(response.available_actions) == 1:
                        requests.make_request(game_pb2.PlayGameRequest(action = response.available_actions[0]))
                        continue

                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.GameResult:
                        is_finalized = True
                        agent.on_game_end(state, response.game_result)
                        requests.make_request(game_pb2.PlayGameRequest(action = ControllerActions.ConfirmEndGame))
                        continue

                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.RoundResult:
                        outcome = response.round_evaluation
                        result  = response.inf_set
                        
                        _, cards, *moves = result.split('.')

                        # In case if there was no showdown, we replace resulting '?' with our hand (if available)
                        if cards == '??':
                            _clist = list(cards)
                            _clist[int(state.get_last_round_state().get_turn_order()) - 1] = state.get_last_round_state().get_card()[0]
                            _cards = "".join(_clist)
                        else:
                            _cards = cards

                        state.get_last_round_state().set_moves_history(moves)
                        state.get_last_round_state().set_outcome(outcome)
                        state.get_last_round_state().set_cards(_cards)
                        state.update_bank(outcome)
                        agent.on_round_end(state, state.get_last_round_state())
                        state.start_new_round()
                        agent.on_new_round_request(state)
                        requests.make_request(game_pb2.PlayGameRequest(action = ControllerActions.NewRound))

                    if response.event == game_pb2.PlayGameResponse.PlayGameResponseEvent.NextAction:
                        state.get_last_round_state().set_available_actions(response.available_actions)
                        if len(response.inf_set) != 0:
                            state.get_last_round_state().add_move_history(response.inf_set.split('.')[-1])
                        next_action = agent.make_action(state, state.get_last_round_state())
                        state.get_last_round_state().add_move_history(f'{next_action}')
                        requests.make_request(game_pb2.PlayGameRequest(action = next_action))

                requests.close()

                return state
        except grpc.RpcError as grpc_error:
            print(f'Error code: {grpc_error.code()}\nDetails: {grpc_error.details()}')
