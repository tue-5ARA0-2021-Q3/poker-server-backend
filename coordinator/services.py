from curses import meta
import queue
import traceback
import threading
import logging
from coordinator.kuhn.kuhn_constants import resolve_kuhn_type
from coordinator.kuhn.kuhn_coordinator import KuhnCoordinator

from coordinator.kuhn.kuhn_lobby import KuhnGameLobby, KuhnGameLobbyEvents, KuhnGameLobbyMessage, CoordinatorActions
from coordinator.kuhn.kuhn_player import KuhnGameLobbyPlayer, KuhnGameLobbyPlayerMessage

from django_grpc_framework.services import Service
from coordinator.kuhn.kuhn_waiting_room import KuhnWaitingRoom
from coordinator.models import Game, GameCoordinator, GameCoordinatorTypes, GameTypes, Player, PlayerTypes
from coordinator.utilities.card import Card
from proto.game import game_pb2
from django.conf import settings
from enum import Enum

class GameCoordinatorService(Service):
    game_lobbies      = []
    coordinators = {}
    lock         = threading.Lock()
    logger       = logging.getLogger('service.coordinator')

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def Create(self, request, context):
        player = Player.objects.get(token = request.token)

        if player.is_disabled:
            raise Exception(f'User is disabled')

        game_type = resolve_kuhn_type(request.kuhn_type)

        # Players can only create private games with DUEL type and only against real players
        coordinator = GameCoordinatorService.add_coordinator(KuhnCoordinator(
            coordinator_type = GameCoordinatorTypes.DUEL_PLAYER_PLAYER,
            game_type        = game_type,
            capacity         = 2,
            timeout          = settings.COORDINATOR_CONNECTION_TIMEOUT,
            is_private       = True
        ))

        return game_pb2.CreateGameResponse(id = str(coordinator.id))

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def Play(self, request, context):

        # First check method's metadata and extract player's secret token
        metadata  = dict(context.invocation_metadata())
        token     = metadata['token']

        player = Player.objects.get(token = token)

        if player.is_disabled:
            raise Exception(f'User is disabled')

        game_type      = resolve_kuhn_type(metadata['kuhn_type'])
        coordinator    = GameCoordinatorService.find_coordinator_instance(player, metadata['game_id'], game_type)
        coordinator_id = coordinator.id

        GameCoordinatorService.logger.info(f'Player { token } is trying to connect to the coordinator with id = { coordinator_id }')

        if coordinator.is_closed():
            GameCoordinatorService.logger.warning(f'Attempt to connect to a closed coordinator { coordinator_id }')
            raise Exception('Coordinator has been closed already')

        callback_active = True

        def GRPCConnectionTerminationCallback():
            if callback_active:
                if coordinator.waiting_room.is_player_registered(token) and not coordinator.is_closed():
                    coordinator.close(error = f'Coordinator has been terminated before it finished. Another player possibly has disconnected from the game due to an exception.')
                    GameCoordinatorService.remove_coordinator(coordinator)

        context.add_callback(GRPCConnectionTerminationCallback)

        # In general event flow is the following
        # Both players first send 'CONNECT' event which server simply ignores, because it register them anyway on first connect attempt
        # Once both players have been connected lobby sends an initial `GameStart` event (see `game_lobby_coordinator` function)
        # `GameStart` event triggers both players to request list of their available actions
        #    - in the beggining both players receive only one available actions: request a new round
        # When both players requested a new round the lobby randomly decides who goes first and send a `CardDeal` event
        # `CardDeal` event triggers both players to request list of their available actions again
        #    - list of available actions at this moment depends on play order
        #    - first player in order receives real actions, like BET or CHECK
        #    - second player in order simply receives WAIT
        # Player commit their actions in a ping-pong manner with `NextAction` event
        # Once game round reaches `terminal` stage server sends `RoundResult` event
        # `RoundResult` event triggers both players to request a new round
        #     - if both players have enough bank to continue server replies with a `CardDeal` event
        #     - otherwise server replies with a `GameResult` event
        # `GameResult` event triggers both players to request list of their available actions again
        #     - in tournament mode players may receive `WAIT` event and wait for their next game
        #     - in non-tournament mode players always receive `Close` event at this stage
        try:

            if metadata['game_id'] == 'random':
                yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.UpdateGameId, game_id = str(coordinator_id))

            # Each player should register themself in the game coordinator lobby
            coordinator.waiting_room.register_player(token)

            is_ready = coordinator.waiting_room.wait_ready()

            if not is_ready:
                coordinator.close(error = f'Timeout in waiting room. Not enough players to play with.')
                GameCoordinatorService.remove_coordinator(coordinator)
                yield game_pb2.PlayGameResponse(
                    event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Error, 
                    error = 'Timeout in waiting room. Not enough players to play with.'
                )
                return

            # Each player has its unique channel to communicate with the game coordinator lobby
            player_channel = coordinator.waiting_room.get_player_channel(token)

            # We run this inner loop until we have some messages from connected player
            for message in request:

                # In case if lobby has been finished, but player requests a list of available actions just 
                # send a `Close` disconnect event and break out of the loop since we do not expect any other message after that
                if message.action == CoordinatorActions.AvailableActions and coordinator.is_closed():
                    coordinator.logger.info(f'Sending disconnect event to the player { token }')
                    yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Close)
                    break

                # Check against utility messages: 'CONNECT' and 'WAIT'
                # In principle this messages do nothing, but can be used to initiate a new game or to wait for another player action
                if message.action != CoordinatorActions.Connect and message.action != CoordinatorActions.Wait:
                    coordinator.channel.put(KuhnGameLobbyPlayerMessage(token, message.action))

                # Waiting for a response from the game coordinator about another player's decision and available actions
                response = None
                while (not coordinator.is_closed() and response is None) or not player_channel.empty():
                    try:
                        response = player_channel.get(timeout = settings.COORDINATOR_WAITING_TIMEOUT)
                        if isinstance(response, KuhnGameLobbyMessage):
                            if response.event == KuhnGameLobbyEvents.GameStart:
                                yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.GameStart)
                            # If response is a `CardDeal` we generate a new card based on its rank 
                            # and send the corresponding turn order, card rank (if enabled in server settings) and the image itself in a form of raw bytes
                            # Note that depending on the turn order the list of available actions may be different
                            # First player in order gets a list of possible moves
                            # Second player in order gets an only one command to wait for a move from the first player
                            # In case of a `CardDeal` event we expect lobby to send
                            # - turn_order
                            # - card
                            # - actions 
                            elif response.event == KuhnGameLobbyEvents.CardDeal:
                                turn_order = response.data['turn_order']
                                card_rank  = response.data['card'] if settings.COORDINATOR_REVEAL_CARDS else '?'
                                actions    = response.data['actions']
                                card_image = Card(response.data['card'], lobby.get_valid_card_ranks()).get_image().tobytes('raw')
                                yield game_pb2.PlayGameResponse(
                                    event = game_pb2.PlayGameResponse.PlayGameResponseEvent.CardDeal, 
                                    available_actions = actions, 
                                    turn_order = turn_order,
                                    card_rank  = card_rank,
                                    card_image = card_image
                                )
                            # In case of a `NextAction` event we expect lobby to send
                            # - inf_set
                            # - actions
                            elif response.event == KuhnGameLobbyEvents.NextAction:                                
                                yield game_pb2.PlayGameResponse(
                                    event = game_pb2.PlayGameResponse.PlayGameResponseEvent.NextAction,
                                    inf_set           = response.data['inf_set'],
                                    available_actions = response.data['actions'] 
                                )
                            # In case of a `RoundResult` event we expect lobby to send
                            # - evaluation
                            # - inf_set
                            elif response.event == KuhnGameLobbyEvents.RoundResult:
                                yield game_pb2.PlayGameResponse(
                                    event = game_pb2.PlayGameResponse.PlayGameResponseEvent.RoundResult,
                                    round_evaluation = response.data['evaluation'],
                                    inf_set          = response.data['inf_set']
                                )
                            # In case of a `GameResult` event we expect lobby to send
                            # - game_result
                            elif response.event == KuhnGameLobbyEvents.GameResult:
                                yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.GameResult, game_result = response.data['game_result'])
                            # In case of a `GameResult` event we expect lobby to send
                            # - error
                            elif response.event == KuhnGameLobbyEvents.Error:
                                yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Error, error = response.data['error'])
                                coordinator.close(error = response.data['error'])
                            else:
                                raise Exception(f'Unexpected event type from lobby response: { response }')
                        else:
                            raise Exception(f'Unexpected response type from lobby: { response }')
                    except queue.Empty:
                        if coordinator.is_closed() and player_channel.empty():
                            coordinator.logger.error(f'Coordinator has been finished while waiting for response from player.')
                            return

            callback_active = False

            if coordinator.waiting_room.is_player_registered(token):
                GameCoordinatorService.remove_coordinator(coordinator)

        except KuhnCoordinator.CoordinatorWaitingRoomCreationFailed:
            GameCoordinatorService.logger.error(f'Connection error. Failed to create a waiting room.')
            yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Error, error = 'Failed to create a waiting room.')
        except KuhnWaitingRoom.WaitingRoomIsFull:
            GameCoordinatorService.logger.error(f'Connection error. Coordinator waiting room is full.')
            yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Error, error = 'Coordinator waiting room is full.')
        except KuhnWaitingRoom.WaitingRoomIsClosed:
            GameCoordinatorService.logger.error(f'Connection error. Coordinator waiting room is closed.')
            yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Error, error = 'Coordinator waiting room is closed.')
        except KuhnWaitingRoom.PlayerDoubleRegistration:
            GameCoordinatorService.logger.error(f'Connection error. Player with the same id has been registered already exist in this waiting room.')
            yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Error, error = 'Player with the same id has been registered already exist in this waiting room.')
        except Exception as e:
            if len(str(e)) != 0:
                GameCoordinatorService.logger.error(f'Connection error. Unhandled exception: { e }.\n')
                traceback.print_exc()
                yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Error, error = f'Unexpected error on server side: { e }. Please report.\n')
                if coordinator != None and coordinator.waiting_room != None and coordinator.waiting_room.is_player_registered(token):
                    coordinator.close(error = str(e))
                    GameCoordinatorService.remove_coordinator(coordinator)

        callback_active = False

    @staticmethod
    def add_coordinator(coordinator: KuhnCoordinator) -> KuhnCoordinator:
        with GameCoordinatorService.lock:
            if not coordinator.id in GameCoordinatorService.coordinators:
                GameCoordinatorService.coordinators[coordinator.id] = coordinator
                GameCoordinatorService.logger.info(f'Added game coordinator { coordinator.id }')
            else:
                GameCoordinatorService.logger.warning(f'Trying to add the same game coordinator { coordinator.id }')
        return coordinator

    @staticmethod
    def remove_coordinator(coordinator: KuhnCoordinator) -> KuhnCoordinator:
        with GameCoordinatorService.lock:
            if coordinator.id in GameCoordinatorService.coordinators:
                GameCoordinatorService.coordinators.pop(coordinator.id)
                GameCoordinatorService.logger.info(f'Removed game coordinator { coordinator.id }')
        return coordinator

    @staticmethod 
    def find_coordinator_instance(player: Player, coordinator_id: str, game_type: int) -> KuhnCoordinator:
        # Behaviour depends on provided `token`. 
        # Real players attemt to find `PLAYER_PLAYER` games only
        # Bot players attempt to find `PLAYER_BOT` games only
        # First we check if requested game is a game against a bot
        # In this case we always create a new private game and will add a bot to it later on
        if coordinator_id == 'bot':
            if player.is_bot:
                raise Exception('Bots cannot play agains bots')
            return GameCoordinatorService.add_coordinator(KuhnCoordinator(
                coordinator_type = GameCoordinatorTypes.DUEL_PLAYER_BOT, 
                game_type        = game_type, 
                capacity         = 2,
                timeout          = settings.COORDINATOR_CONNECTION_TIMEOUT,
                is_private       = True
            ))
        # Second we check if requested game was a random game
        # In this case we check if there are some public pending games available and do nothing if not
        # Random games can be played only with real players, but Kuhn type game should match
        elif coordinator_id == 'random':
            if player.is_bot:
                raise Exception('Bots cannot play random games')
            # If we can find a public unfinished game we simply return it
            # This procedure assumes there are no concurrent connection, however 
            # in case of concurrent connections one of the connection should not have enough time to connect
            public_coordinators = GameCoordinator.objects.filter(
                coordinator_type = GameCoordinatorTypes.DUEL_PLAYER_PLAYER, 
                game_type        = game_type, 
                is_started       = False,
                is_failed        = False, 
                is_finished      = False, 
                is_private       = False
            )
            if len(public_coordinators) != 0:
                coordinator = public_coordinators[0] # We pick first available public coordinator
                return GameCoordinatorService.coordinators[coordinator.id] # Coordinator must exist in service internal dict
            else:
                # In case if game_id was random and there are no games available at the moment we create a new one
                return GameCoordinatorService.add_coordinator(KuhnCoordinator(
                    coordinator_type = GameCoordinatorTypes.DUEL_PLAYER_PLAYER,
                    game_type        = game_type,
                    capacity         = 2,
                    is_private       = False
                ))
        else:
            # Last case should be a valid game_id otherwise we return an error
            coordinator_type = GameCoordinatorTypes.DUEL_PLAYER_PLAYER if not player.is_bot else GameCoordinatorTypes.DUEL_PLAYER_BOT
            candidates = GameCoordinator.objects.filter(id = coordinator_id, coordinator_type = coordinator_type, game_type = game_type)
            if len(candidates) != 0:
                coordinator = candidates[0]
                return GameCoordinatorService.coordinators[coordinator.id]
            raise Exception(f'Coordinator instance with UUID { coordinator_id } has not been found') 
