import logging
import threading
import time
from django.apps import AppConfig
from django.conf import settings

class CoordinatorConfig(AppConfig):
    name = 'coordinator'

    def start_grpc_server(self, game_pb2_grpc, servicer):
        import grpc
        from concurrent import futures
        from django.conf import settings
        from django_grpc_framework.settings import grpc_settings

        thread_pool  = futures.ThreadPoolExecutor(max_workers = settings.GRPC_MAX_WORKERS)
        interceptors = grpc_settings.SERVER_INTERCEPTORS
        server = grpc.server(thread_pool, interceptors = interceptors)

        grpc_settings.ROOT_HANDLERS_HOOK(server)

        server.add_insecure_port(settings.GRPC_SERVER_ADDRPORT)

        game_pb2_grpc.add_GameCoordinatorControllerServicer_to_server(servicer, server)

        print(f'Starting GRPC server at { settings.GRPC_SERVER_ADDRPORT }.')

        server.start()
        server.wait_for_termination()

    def ready(self):
        
        from coordinator.services import GameCoordinatorService
        from proto.game import game_pb2_grpc

        # This line is important
        import coordinator.signals

        servicer = GameCoordinatorService.as_servicer()

        grpc_thread        = threading.Thread(target = self.start_grpc_server, args = (game_pb2_grpc, servicer))
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
