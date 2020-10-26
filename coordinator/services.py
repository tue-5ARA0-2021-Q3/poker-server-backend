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
    games = []
    games_lock = threading.Lock()

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def Create(self, request, context):
        player = Player.objects.get(token=request.token)
        newgame = Game(created_by=player.token, game_type=GameTypes.PLAYER_PLAYER)
        newgame.save()
        return game_pb2.CreateGameResponse(id=str(newgame.id))

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def List(self, request, context):
        player = Player.objects.get(token=request.token)
        games = Game.objects.filter(created_by=player.token)
        return game_pb2.ListGameResponse(game_ids=list(map(lambda game: str(game.id), games)))

    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def Play(self, request, context):
        metadata = dict(context.invocation_metadata())
        token = metadata['token']
        gameid = metadata['gameid']

        game_db = Game.objects.get(id=gameid)

        if game_db.is_finished:
            raise Exception('Game is finished')

        with GameCoordinatorService.games_lock:
            game_instances = list(filter(lambda game: game.gameid == gameid, GameCoordinatorService.games))
            if len(game_instances) == 0:
                instance = KuhnPokerGameInstance(gameid)
                GameCoordinatorService.games.append(instance)
            else:
                instance = game_instances[0]

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
                    yield game_pb2.PlayGameResponse(state=instance.stage.secret_inf_set(),
                                                    available_actions=instance.get_available_actions())
                elif instance.is_secondary_player(token):
                    instance.wait_for_opponent(token)
                    yield game_pb2.PlayGameResponse(state=instance.stage.secret_inf_set(),
                                                    available_actions=instance.get_available_actions())
            elif instance.is_results_action(action):
                if instance.is_primary_player(token):
                    instance.update_players_bank()
                    instance.wait_for_opponent(token)
                elif instance.is_secondary_player(token):
                    instance.notify_opponent(token, sync=True)

                if instance.player1.get_current_bank() > 0 and instance.player2.get_current_bank() > 0:
                    yield game_pb2.PlayGameResponse(state=NEXT, available_actions=instance.get_restart_actions())
                else:
                    yield game_pb2.PlayGameResponse(state=instance.game_result(token),
                                                    available_actions=instance.get_end_actions())

            elif instance.is_end_action(action):
                break
            else:
                instance.stage = instance.stage.play(action)
                instance.notify_opponent(token)
                instance.wait_for_opponent(token)
                if not instance.stage.is_terminal():
                    yield game_pb2.PlayGameResponse(state=instance.stage.secret_inf_set(),
                                                    available_actions=instance.get_available_actions())
                else:
                    instance.notify_opponent(token)
                    yield game_pb2.PlayGameResponse(state=instance.stage.inf_set(),
                                                    available_actions=instance.get_results_actions())

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
