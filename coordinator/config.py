import logging
import threading
import sys
import grpc
import os
from concurrent import futures
from django.conf import settings
from django_grpc_framework.settings import grpc_settings
from django.apps import AppConfig
from django.utils.autoreload import get_reloader, ensure_echo_on, check_errors, WatchmanUnavailable, restart_with_reloader

class CoordinatorConfig(AppConfig):
    name = 'coordinator'

    def start_grpc_server(self):
        try: 

            def __start_grpc_server():
                print(f'Starting GRPC server at { settings.GRPC_SERVER_ADDRPORT }.')
                server = grpc.server(futures.ThreadPoolExecutor(max_workers = settings.GRPC_MAX_WORKERS), interceptors = grpc_settings.SERVER_INTERCEPTORS)
                grpc_settings.ROOT_HANDLERS_HOOK(server)
                server.add_insecure_port(settings.GRPC_SERVER_ADDRPORT)
                server.start()
                server.wait_for_termination()

            if not settings.GRPC_USE_RELOADER:
                __start_grpc_server()
            elif settings.GRPC_USE_RELOADER and os.environ.get('RUN_MAIN') == 'true':
                reloader = get_reloader()
                print(f'Watching for file changes in gRPC server with { reloader.__class__.__name__ }')
                ensure_echo_on()

                __main_func = check_errors(__start_grpc_server)
                django_grpc_framework_main_thread = threading.Thread(target = __main_func, name='django-grpc-framework-main-thread')
                django_grpc_framework_main_thread.daemon = True
                django_grpc_framework_main_thread.start()

                while not reloader.should_stop:
                    try:
                        reloader.run(django_grpc_framework_main_thread)
                    except WatchmanUnavailable as ex:
                        # It's possible that the watchman service shuts down or otherwise
                        # becomes unavailable. In that case, use the StatReloader.
                        logging.error('Error connecting to Watchman: %s', ex)
            
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
