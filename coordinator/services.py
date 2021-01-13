import grpc
import sys
import threading

from coordinator.games.kuhn_lobby import KuhnGameLobby, KuhnGameLobbyPlayerMessage, KuhnGameLobbyStageMessage, KuhnGameLobbyStageError, \
    KuhnGameLobbyStageCardDeal
from django_grpc_framework.services import Service
from coordinator.models import Game, Player, GameTypes
from coordinator.utilities.card import Card
from proto.game import game_pb2


class GameCoordinatorService(Service):
    game_lobbies = []
    games_lock = threading.Lock()

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def Create(self, request, context):
        player = Player.objects.get(token = request.token)
        new_game = Game(created_by = player.token, game_type = GameTypes.PLAYER_PLAYER)
        instance = GameCoordinatorService.create_game_lobby_instance(new_game.id)
        if instance is not None:
            new_game.save()
            return game_pb2.CreateGameResponse(id = str(new_game.id))
        else:
            raise Exception(f'Failed to create a game instance: {new_game.id}')

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def FindOrCreate(self, request, context):
        player = Player.objects.get(token = request.token)
        game_candidates = Game.objects.filter(game_type = GameTypes.PLAYER_PLAYER, is_started = False,
                                              is_failed = False, is_finished = False)
        if len(game_candidates) == 0:
            new_game = Game(created_by = player.token, game_type = GameTypes.PLAYER_PLAYER)
            instance = GameCoordinatorService.create_game_lobby_instance(new_game.id)
            if instance is not None:
                new_game.save()
                return game_pb2.ListGameResponse(game_ids = [str(new_game.id)])
            else:
                raise Exception(f'Failed to create a game instance: {new_game.id}')
        else:
            return game_pb2.ListGameResponse(game_ids = list(map(lambda candidate: str(candidate.id), game_candidates)))

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def List(self, request, context):
        player = Player.objects.get(token = request.token)
        games = Game.objects.filter(created_by = player.token)
        return game_pb2.ListGameResponse(game_ids = list(map(lambda game: str(game.id), games)))

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def Play(self, request, context):
        # First check method's metadata and extract player's secret token and game_id
        metadata = dict(context.invocation_metadata())
        token = metadata['token']
        game_id = metadata['game_id']
        lobby = GameCoordinatorService.create_game_lobby_instance(game_id)

        try:
            # We look up for a game object in database
            # It should exist at this point otherwise function throws an error and game ends immediately
            game_db = Game.objects.get(id = game_id)

            if game_db.is_finished:
                raise Exception('Game is finished')

            # First connected player creates a game coordinator
            # Second connected player does not create a new game coordinator, but reuses the same one
            lobby.start()

            # Each player should register themself in the game coordinator lobby
            lobby.register_player(token)
            lobby.wait_for_players()

            # Each player has its unique channel to communicate with the game coordinator lobby
            player_channel = lobby.get_player_channel(token)

            # We run this inner loop until we have some messages from connected player
            for message in request:
                # Check against utility messages: 'CONNECT' and 'WAIT'
                # In principle this messages do nothing, but can be used to initiate a new game or to wait for another player action
                if message.action != 'CONNECT' and message.action != 'WAIT':
                    lobby.channel.put(KuhnGameLobbyPlayerMessage(token, message.action))

                # Waiting for a response from the game coordinator about another player's decision and available actions
                response = player_channel.get()

                if isinstance(response, KuhnGameLobbyStageCardDeal):
                    state = f'CARD:{ response.turn_order }:{ response.card }'
                    actions = response.actions
                    card_image = Card(response.card).get_image(0.1).tobytes('raw')
                    yield game_pb2.PlayGameResponse(state = state, available_actions = actions, card_image = card_image)
                # Normally the game coordinator returns an instance of KuhnGameLobbyStageMessage
                # It contains 'state' and 'available_actions' fields
                # Server redirects this information to a player's agent and will wait for its decision in a next message
                elif isinstance(response, KuhnGameLobbyStageMessage):
                    state = response.state
                    actions = response.actions
                    yield game_pb2.PlayGameResponse(state = state, available_actions = actions)
                # It might happen that some error has been occurred
                # In this case we just notify player's agent and close the lobby
                elif isinstance(response, KuhnGameLobbyStageError):
                    yield game_pb2.PlayGameResponse(state = f'ERROR:{response.error}', available_actions = [])
                    lobby.finish(error = response.error)
                    break

            if lobby.is_player_registered(token):
                GameCoordinatorService.remove_game_lobby_instance(game_id)
        except grpc.RpcError:
            pass
        except KuhnGameLobby.GameLobbyFullError:
            yield game_pb2.PlayGameResponse(state = f'ERROR: Game lobby is full', available_actions = [])
        except KuhnGameLobby.PlayerAlreadyExistError:
            yield game_pb2.PlayGameResponse(state = f'ERROR: Player with the same id is already exist in this lobby',
                                            available_actions = [])
        except Exception as e:
            yield game_pb2.PlayGameResponse(state = f'ERROR:{e}', available_actions = [])
            if lobby.is_player_registered(token):
                GameCoordinatorService.remove_game_lobby_instance(game_id)

    @staticmethod
    def create_game_lobby_instance(game_id: str) -> KuhnGameLobby:
        lobby = None
        with GameCoordinatorService.games_lock:
            game_lobbies = list(filter(lambda game: game.game_id == game_id, GameCoordinatorService.game_lobbies))
            if len(game_lobbies) == 0:
                lobby = KuhnGameLobby(game_id)
                GameCoordinatorService.game_lobbies.append(lobby)
            else:
                lobby = game_lobbies[0]
        return lobby

    @staticmethod
    def get_game_lobby_instance(game_id: str) -> KuhnGameLobby:
        lobby = None
        with GameCoordinatorService.games_lock:
            game_lobbies = list(filter(lambda game: game.game_id == game_id, GameCoordinatorService.game_lobbies))
            if len(game_lobbies) == 0:
                raise Exception(f'There is no game lobby instance with id: {game_id}')
            else:
                lobby = game_lobbies[0]
        return lobby

    @staticmethod
    def remove_game_lobby_instance(game_id: str):
        with GameCoordinatorService.games_lock:
            game_lobbies = list(filter(lambda game: game.game_id == game_id, GameCoordinatorService.game_lobbies))
            for lobby in game_lobbies:
                GameCoordinatorService.game_lobbies.remove(lobby)
