import grpc
import sys
import threading

from coordinator.games.kuhn_lobby import KuhnGameLobby, KuhnGameLobbyPlayerMessage, KuhnGameLobbyStageMessage, KuhnGameLobbyStageError
from django_grpc_framework.services import Service
from coordinator.models import Game, Player, GameTypes
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
        token, game_id = metadata['token'], metadata['game_id']

        # We look up for a game object in database
        # It should exist at this point otherwise function throws an error and game ends immediately
        game_db = Game.objects.get(id = game_id)

        if game_db.is_finished:
            raise Exception('Game is finished')

        # First connected player creates a game coordinator
        # Second connected player does not create a new game coordinator, but reuses the same one
        lobby = GameCoordinatorService.create_game_lobby_instance(game_id)
        lobby.start()

        # Each player should register themself in the game coordinator lobby
        lobby.register_player(token)
        lobby.wait_for_players()

        # Each player has its unique channel to communicate with the game coordinator lobby
        player_channel = lobby.get_player_channel(token)

        try:
            # We run this inner loop until we have some messages from connected player
            for message in request:
                # Check against utility messages: 'CONNECT' and 'WAIT'
                # In principle this messages do nothing, but can be used to initiate a new game or to wait for another player action
                if message.action != 'CONNECT' and message.action != 'WAIT':
                    lobby.channel.put(KuhnGameLobbyPlayerMessage(token, message.action))

                # Waiting for a response from the game coordinator about another player's decision and available actions
                response = player_channel.get()

                # Normally the game coordinator returns an instance of KuhnGameLobbyStageMessage
                # It contains 'state' and 'available_actions' fields
                # Server redirects this information to a player's agent and will wait for its decision in a next message
                if isinstance(response, KuhnGameLobbyStageMessage):
                    state = response.state
                    actions = response.actions
                    yield game_pb2.PlayGameResponse(state = state, available_actions = actions)
                # It might happen that some error has been occurred
                # In this case we just notify player's agent and close the lobby
                elif isinstance(response, KuhnGameLobbyStageError):
                    yield game_pb2.PlayGameResponse(state = f'ERROR:{response.error}', available_actions = [])
                    lobby.close(error = response.error)
                    break
        except grpc.RpcError:
            pass
        except Exception as e:
            print('Unhandled exception: ', e)
            print(sys.exc_info())
        finally:
            GameCoordinatorService.remove_game_lobby_instance(game_id)

        # # time.sleep(1.0)

        # if instance.is_opponent_waiting(token):
        #     instance.notify_opponent(token)

        # # Game.objects.update(id = game_id, is_finished = True)
        # if instance.is_primary_player(token):
        #     with GameCoordinatorService.games_lock:
        #         try:
        #             instance.finish_game()
        #             game_db = Game.objects.get(id = game_id)
        #             game_db.is_finished = True
        #             game_db.winner_id = instance.get_winner_id()
        #             game_db.outcome = instance.get_outcomes()
        #             game_db.save(update_fields = [ 'is_finished', 'winner_id', 'outcome' ])
        #             GameCoordinatorService.games.remove(instance)
        #         except:
        #             print("Unexpected error:", sys.exc_info()[ 0 ])
        #             return

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
