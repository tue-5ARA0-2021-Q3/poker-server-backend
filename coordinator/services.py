import uuid
import grpc
import sys
import os
import queue
import traceback
import threading
from coordinator import models

from coordinator.games.kuhn_lobby import KuhnGameLobby, KuhnGameLobbyEvents, KuhnGameLobbyMessage, KuhnGameLobbyPlayerMessage

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

                # In case if lobby has been finished, but player requests a list of available actions just 
                # send a `Close` disconnect event and break out of the loop since we do not expect any other message after that
                if message.action == 'AVAILABLE_ACTIONS' and lobby.is_finished():
                    lobby.get_logger().info(f'Sending disconnect event to the player { token }')
                    yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Close)
                    break

                # Check against utility messages: 'CONNECT' and 'WAIT'
                # In principle this messages do nothing, but can be used to initiate a new game or to wait for another player action
                if message.action != 'CONNECT' and message.action != 'WAIT':
                    lobby.channel.put(KuhnGameLobbyPlayerMessage(token, message.action))

                # Waiting for a response from the game coordinator about another player's decision and available actions
                response = None
                while (not lobby.is_finished() and response is None) or not player_channel.empty():
                    try:
                        response = player_channel.get(timeout = 5)
                        # If response is a `KuhnGameLobbyStageCardDeal` we generate a new card based on its rank 
                        # and send the corresponding turn order, card rank (if enabled in server settings) and the image itself in a form of raw bytes
                        # Note that depending on the turn order the list of available actions may be different
                        # First player in order gets a list of possible moves
                        # Second player in order gets an only one command to wait for a move from the first player
                        if isinstance(response, KuhnGameLobbyMessage):
                            if response.event == KuhnGameLobbyEvents.GameStart:
                                yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.GameStart)
                            # In case of a `CardDeal` event we expect lobby to send
                            # - turn_order
                            # - card
                            # - actions 
                            elif response.event == KuhnGameLobbyEvents.CardDeal:
                                turn_order = response.data['turn_order']
                                card_rank  = response.data['card'] if settings.LOBBY_REVEAL_CARDS else '?'
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
                                lobby.finish(error = response.data['error'])
                            else:
                                raise Exception(f'Unexpected event type from lobby response: { response }')
                        else:
                            raise Exception(f'Unexpected response type from lobby: { response }')
                    except queue.Empty:
                        if lobby.is_finished() and player_channel.empty():
                            lobby.get_logger().error(f'Lobby has been finished while waiting for response from player.')
                            return

            callback_active = False

            if lobby.is_player_registered(token):
                GameCoordinatorService.remove_game_lobby_instance(game_id)

        except KuhnGameLobby.GameLobbyFullError:
            lobby.get_logger().error(f'Connection error. Game lobby is full.')
            yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Error, error = 'Gamme lobby is full')
        except KuhnGameLobby.PlayerAlreadyExistError:
            lobby.get_logger().error(f'Connection error. Player with the same id is already exist in this lobby')
            yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Error, error = 'Player with the same id is already exist in this lobby')
        except Exception as e:
            if len(str(e)) != 0:
                lobby.get_logger().error(f'Connection error. Unhandled exception: { e }.\n')
                traceback.print_exc()
                yield game_pb2.PlayGameResponse(event = game_pb2.PlayGameResponse.PlayGameResponseEvent.Error, error = f'Unexpected error on server side: { e }. Please report.\n')
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
