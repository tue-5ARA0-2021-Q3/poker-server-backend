import uuid
import grpc
import sys
import os
import queue
import threading

from coordinator.games.kuhn_lobby import KuhnGameLobby, KuhnGameLobbyPlayerMessage, KuhnGameLobbyStageMessage, KuhnGameLobbyStageError, \
    KuhnGameLobbyStageCardDeal

from django_grpc_framework.services import Service
from coordinator.models import Game, Player, PlayerTypes
from coordinator.utilities.card import Card
from proto.game import game_pb2
from django.conf import settings


class GameCoordinatorService(Service):
    game_lobbies = []
    games_lock = threading.Lock()

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def Create(self, request, context):
        player = Player.objects.get(token = request.token)

        if player.is_disabled:
            raise Exception(f'User is disabled')

        kuhn_type = KuhnGameLobby.resolve_kuhn_type(request.kuhn_type)
        new_game  = Game(created_by = player.token, player_type = PlayerTypes.PLAYER_PLAYER, kuhn_type = kuhn_type, is_private = True)
        instance  = GameCoordinatorService.find_or_create_game_lobby_instance(new_game)
        if instance is not None:
            new_game.save()
            return game_pb2.CreateGameResponse(id = str(new_game.id))
        else:
            raise Exception(f'Failed to create a game instance: {new_game.id}')

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def FindOrCreate(self, request, context):
        player = Player.objects.get(token = request.token)

        if player.is_disabled:
            raise Exception(f'User is disabled')

        kuhn_type = KuhnGameLobby.resolve_kuhn_type(request.kuhn_type)
        game_candidates = Game.objects.filter(player_type = PlayerTypes.PLAYER_PLAYER, kuhn_type = kuhn_type, is_started = False,
                                              is_failed = False, is_finished = False, is_private = False)
        if len(game_candidates) == 0:
            new_game = Game(created_by = player.token, player_type = PlayerTypes.PLAYER_PLAYER, kuhn_type = kuhn_type, is_private = False)
            instance = GameCoordinatorService.find_or_create_game_lobby_instance(new_game)
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

        if player.is_disabled:
            raise Exception(f'User is disabled')

        games = Game.objects.filter(created_by = player.token)
        return game_pb2.ListGameResponse(game_ids = list(map(lambda game: str(game.id), games)))

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def Play(self, request, context):

        # First check method's metadata and extract player's secret token and game_id
        metadata = dict(context.invocation_metadata())
        token = metadata['token']
        kuhn_type = KuhnGameLobby.resolve_kuhn_type(metadata['kuhn_type'])

        player = Player.objects.get(token = token)

        if player.is_disabled:
            raise Exception(f'User is disabled')

        game    = GameCoordinatorService.find_game_instance(token, metadata['game_id'], kuhn_type)
        lobby   = GameCoordinatorService.find_or_create_game_lobby_instance(game)
        game_id = game.id

        lobby.get_logger().info(f'Player {token} is trying to connect to the lobby with game id {game_id}')

        callback_active = True

        def GRPCConnectionTerminationCallback():
            if callback_active:
                if lobby.is_player_registered(token) and not lobby.is_finished():
                    lobby.get_logger().error(f'Lobby has been terminated before its finished')
                    lobby.finish(error = f'Lobby terminated before its finished. Another player possible '
                                         f'has disconnected from the game due to exception.')
                    GameCoordinatorService.remove_game_lobby_instance(game_id)

        context.add_callback(GRPCConnectionTerminationCallback)

        try:
            # We look up for a game object in database
            # It should exist at this point otherwise function throws an error and game ends immediately
            game_db = Game.objects.get(id = game_id)

            if game_db.is_finished:
                lobby.get_logger().error(f'Game has been finished already')
                raise Exception('Game has been finished already')

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
                response = None
                while (not lobby.is_finished() and response is None) or not player_channel.empty():
                    try:
                        response = player_channel.get(timeout = 1)
                    except queue.Empty:
                        if lobby.is_finished() and player_channel.empty():
                            lobby.get_logger().error(f'Lobby has been finished while waiting for response from player.')
                            return
                if isinstance(response, KuhnGameLobbyStageCardDeal):
                    state = f'CARD:{response.turn_order}:{response.card}' if settings.LOBBY_REVEAL_CARDS else f'CARD:{response.turn_order}:?'
                    actions = response.actions
                    card_image = Card(response.card, lobby.get_valid_card_ranks()).get_image().tobytes('raw')
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

            callback_active = False

            if lobby.is_player_registered(token):
                GameCoordinatorService.remove_game_lobby_instance(game_id)

        except KuhnGameLobby.GameLobbyFullError:
            lobby.get_logger().error(f'Connection error. Game lobby is full.')
            yield game_pb2.PlayGameResponse(state = f'ERROR: Game lobby is full', available_actions = [])
        except KuhnGameLobby.PlayerAlreadyExistError:
            lobby.get_logger().error(f'Connection error. Player with the same id is already exist in this lobby')
            yield game_pb2.PlayGameResponse(state = f'ERROR: Player with the same id is already exist in this lobby',
                                            available_actions = [])
        except Exception as e:
            if len(str(e)) != 0:
                lobby.get_logger().error(f'Connection error. Unhandled exception: {e}')
                yield game_pb2.PlayGameResponse(state = f'ERROR: {e}', available_actions = [])
                if lobby.is_player_registered(token):
                    GameCoordinatorService.remove_game_lobby_instance(game_id)

        callback_active = False

    @staticmethod 
    def find_game_instance(token: str, game_id: str, kuhn_type: int) -> Game:
        # Behaviour depends on provided `token`. 
        # Real players attemt to find `PLAYER_PLAYER` games only
        # Bot players attempt to find `PLAYER_BOT` games only
        player      = Player.objects.get(token = token)
        # First we check if requested game is a game against a bot
        # In this case we always create a new private game and will add a bot to it later on
        if game_id == 'bot':
            if player.is_bot:
                raise Exception('Bots cannot play agains bots')
            bot_game = Game(created_by = token, player_type = PlayerTypes.PLAYER_BOT, kuhn_type = kuhn_type, is_private = True)
            bot_game.save()
            return bot_game
        # Second we check if requested game was a random game
        # In this case we check if there are some public pending games available and do nothing if not
        # Random games can be played only with real players, but Kuhn type game should match
        elif game_id == 'random':
            if player.is_bot:
                raise Exception('Bots cannot play random games')
            # If we can find a public unfinished game we simply return it
            # This procedure assumes there are no concurrent connection, however 
            # in case of concurrent connections one of the connection shouldnot have enough time to connect
            public_games = Game.objects.filter(player_type = PlayerTypes.PLAYER_PLAYER, kuhn_type = kuhn_type, is_started = False,
                                              is_failed = False, is_finished = False, is_private = False)
            if len(public_games) != 0:
                return public_games[0]
            else:
                # In case if game_id was random and there are no games available at the moment we create a new one
                new_public_game = Game(created_by = token, player_type = PlayerTypes.PLAYER_PLAYER, kuhn_type = kuhn_type, is_private = False)
                new_public_game.save()
                return new_public_game
        else:
            # Last case should be a valid game_id otherwise we return an error
            player_type = PlayerTypes.PLAYER_PLAYER if not player.is_bot else PlayerTypes.PLAYER_BOT
            candidates = Game.objects.filter(id = game_id, player_type = player_type, kuhn_type = kuhn_type)
            if len(candidates) != 0:
                return candidates[0]   
            raise Exception('Game instance with UUID { game_id } has not been found') 

    @staticmethod
    def find_or_create_game_lobby_instance(game: Game) -> KuhnGameLobby:
        # This methods does not create a new game instance if one exists already
        game_id = str(game.id)
        kuhn_type = game.kuhn_type
        player_type = game.player_type

        with GameCoordinatorService.games_lock:
            game_lobbies = list(filter(lambda game: game.game_id == game_id, GameCoordinatorService.game_lobbies))
            if len(game_lobbies) != 0:
                return game_lobbies[0]

            new_lobby = KuhnGameLobby(game_id, kuhn_type, player_type)
            GameCoordinatorService.game_lobbies.append(new_lobby)
            new_lobby.get_logger().info(f'Lobby {game_id} of type {kuhn_type} has been added to GameCoordinatorService')
            return new_lobby

    @staticmethod
    def get_game_lobby_instance(game_id: str) -> KuhnGameLobby:
        with GameCoordinatorService.games_lock:
            game_lobbies = list(filter(lambda game: game.game_id == game_id, GameCoordinatorService.game_lobbies))
            if len(game_lobbies) != 0:
                return game_lobbies[0]
        raise Exception(f'There is no game lobby instance with id: {game_id}')

    @staticmethod
    def remove_game_lobby_instance(game_id: str):
        with GameCoordinatorService.games_lock:
            game_lobbies = list(filter(lambda game: game.game_id == game_id, GameCoordinatorService.game_lobbies))
            for lobby in game_lobbies:
                GameCoordinatorService.game_lobbies.remove(lobby)
