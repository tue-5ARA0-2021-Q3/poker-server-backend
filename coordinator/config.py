import logging
import threading
import time
from django.apps import AppConfig
from django.conf import settings
from grpc_framework.management.commands import grpcrunserver
from grpc_framework.signals import grpc_server_init, grpc_server_started, grpc_server_shutdown

class CoordinatorConfig(AppConfig):
    name = 'coordinator'

    def start_grpc_server(self):
        from django.conf import settings
        command = grpcrunserver.Command()
        command.handle(addrport = settings.GRPC_SERVER_ADDRPORT, max_workers = settings.GRPC_MAX_WORKERS, use_reloader = settings.GRPC_USE_RELOADER)

    def grpc_on_server_init(self, server, **kwargs):
        from coordinator.services import GameCoordinatorService
        from proto.game import game_pb2_grpc
        game_pb2_grpc.add_GameCoordinatorControllerServicer_to_server(GameCoordinatorService.as_servicer(), server)

    def ready(self):
        grpc_server_init.connect(self.grpc_on_server_init)

        grpc_thread        = threading.Thread(target = self.start_grpc_server)
        grpc_thread.daemon = True
        grpc_thread.start()

        try:
            from coordinator.models import Player 
            from coordinator.models import pick_random_botname

            if settings.GENERATE_TEST_PLAYERS > 0:
                test_players = Player.objects.filter(is_test = True)
                if len(test_players) < settings.GENERATE_TEST_PLAYERS:
                    to_create = settings.GENERATE_TEST_PLAYERS - len(test_players)
                    for _ in range(to_create):
                        test_player = Player(is_test = True)
                        test_player.save()
                
                for player in list(Player.objects.filter(is_test = True)):
                    print(f'Test player token: { player.token }')
        
            if settings.GENERATE_BOT_PLAYERS > 0:
                bot_players = Player.objects.filter(is_bot = True)
                if len(bot_players) < settings.GENERATE_BOT_PLAYERS:
                    to_create = settings.GENERATE_BOT_PLAYERS - len(bot_players)
                    for _ in range(to_create):
                        bot_player = Player(name = pick_random_botname(), is_bot = True)
                        bot_player.save()

        except:
            logging.warning('Exception happened during instantiation of `CoordinatorConfig`')
