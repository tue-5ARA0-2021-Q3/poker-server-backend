import grpc
import time
import threading
import random

from coordinator.games.kuhn_poker import KuhnPokerGameInstance
from coordinator.games.kuhn_game import KuhnRootChanceGameState
from coordinator.games.kuhn_constants import CARDS_DEALINGS, NEXT
from django_grpc_framework.services import Service
from coordinator.models import Game, Player, GameTypes
from proto.game import game_pb2


class GameCoordinatorService(Service):
    games = [ ]
    games_lock = threading.Lock()

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def Create(self, request, context):
        player = Player.objects.get(token = request.token)
        new_game = Game(created_by = player.token, game_type = GameTypes.PLAYER_PLAYER)
        instance = GameCoordinatorService.create_game_instance(new_game.id)
        if instance is not None:
            new_game.save()
            return game_pb2.CreateGameResponse(id = str(new_game.id))
        else:
            raise Exception(f'Failed to create a game instance: {new_game.id}')

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def FindOrCreate(self, request, context):
        player = Player.objects.get(token = request.token)
        with GameCoordinatorService.games_lock:
            game_candidates = Game.objects.filter(game_type = GameTypes.PLAYER_PLAYER, is_started = False,
                                                  is_failed = False, is_finished = False)
            if len(game_candidates) == 0:
                new_game = Game(created_by = player.token, game_type = GameTypes.PLAYER_PLAYER)
                instance = GameCoordinatorService.create_game_instance(new_game.id)
                if instance is not None:
                    new_game.save()
                    return game_pb2.ListGameResponse(game_ids = [ new_game.id ])
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
        metadata = dict(context.invocation_metadata())
        token = metadata[ 'token' ]
        gameid = metadata[ 'gameid' ]

        game_db = Game.objects.get(id = gameid)

        if game_db.is_finished:
            raise Exception('Game is finished')

        instance = GameCoordinatorService.create_game_instance(gameid)

        instance.register_player(token)
        instance.wait_for_all_players()

        for message in request:
            # Some code for actions
            action = message.action

            if instance.is_restart_action(action):
                if instance.is_primary_player(token):
                    instance.root = KuhnRootChanceGameState(CARDS_DEALINGS)
                    instance.stage = instance.root
                    instance.stage = instance.stage.play(random.choice(CARDS_DEALINGS))
                    yield game_pb2.PlayGameResponse(state = instance.stage.secret_inf_set(),
                                                    available_actions = instance.get_available_actions())
                elif instance.is_secondary_player(token):
                    instance.wait_for_opponent(token)
                    yield game_pb2.PlayGameResponse(state = instance.stage.secret_inf_set(),
                                                    available_actions = instance.get_available_actions())
            elif instance.is_results_action(action):
                if instance.is_primary_player(token):
                    instance.update_players_bank()
                    instance.wait_for_opponent(token)
                elif instance.is_secondary_player(token):
                    instance.notify_opponent(token, sync = True)

                if instance.player1.get_current_bank() > 0 and instance.player2.get_current_bank() > 0:
                    yield game_pb2.PlayGameResponse(state = NEXT, available_actions = instance.get_restart_actions())
                else:
                    yield game_pb2.PlayGameResponse(state = instance.game_result(token),
                                                    available_actions = instance.get_end_actions())

            elif instance.is_end_action(action):
                break
            else:
                instance.stage = instance.stage.play(action)
                instance.notify_opponent(token)
                instance.wait_for_opponent(token)
                if not instance.stage.is_terminal():
                    yield game_pb2.PlayGameResponse(state = instance.stage.secret_inf_set(),
                                                    available_actions = instance.get_available_actions())
                else:
                    instance.notify_opponent(token)
                    yield game_pb2.PlayGameResponse(state = instance.stage.inf_set(),
                                                    available_actions = instance.get_results_actions())

        # time.sleep(1.0)

        if instance.is_opponent_waiting(token):
            instance.notify_opponent(token)

        # Game.objects.update(id = gameid, is_finished = True)
        if instance.is_primary_player(token):
            print('Game result: ' + instance.stage.inf_set())
            print('Money: ' + str(instance.stage.evaluation()))

        instance.finish_game()

        with GameCoordinatorService.games_lock:
            try:
                GameCoordinatorService.games.remove(instance)
            except:
                return

    @staticmethod
    def create_game_instance(game_id):
        instance = None
        with GameCoordinatorService.games_lock:
            game_instances = list(filter(lambda game: game.gameid == game_id, GameCoordinatorService.games))
            if len(game_instances) == 0:
                instance = KuhnPokerGameInstance(game_id)
                GameCoordinatorService.games.append(instance)
            else:
                instance = game_instances[ 0 ]
        return instance

    @staticmethod
    def get_game_instance(game_id):
        instance = None
        with GameCoordinatorService.games_lock:
            game_instances = list(filter(lambda game: game.gameid == game_id, GameCoordinatorService.games))
            if len(game_instances) == 0:
                raise Exception(f'There is no game instance with id: {game_id}')
            else:
                instance = game_instances[ 0 ]
        return instance
