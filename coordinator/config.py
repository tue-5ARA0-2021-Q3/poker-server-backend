import logging
import threading
import time
import grpc
from concurrent import futures
from django.conf import settings
from django_grpc_framework.settings import grpc_settings
from django.apps import AppConfig

class CoordinatorConfig(AppConfig):
    name = 'coordinator'

    def start_grpc_server(self):
        try: 
            print(f'Starting GRPC server at { settings.GRPC_SERVER_ADDRPORT }.')
            server = grpc.server(futures.ThreadPoolExecutor(max_workers = settings.GRPC_MAX_WORKERS), interceptors = grpc_settings.SERVER_INTERCEPTORS)
            grpc_settings.ROOT_HANDLERS_HOOK(server)
            server.add_insecure_port(settings.GRPC_SERVER_ADDRPORT)
            server.start()
            server.wait_for_termination()
        except Exception as e:
            print(f'Error occurred during gRPC server instantiation: { e }')

    def ready(self):

        # This line is important to initialise application's signals 
        import coordinator.signals

        # We run gRPC server in background as `daemon` process that should close automatically as soon as server stops
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
