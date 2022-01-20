import threading
import time
from django.apps import AppConfig
from django.conf import settings
from grpc_framework.management.commands import grpcrunserver
from grpc_framework.signals import grpc_server_init, grpc_server_started, grpc_server_shutdown

class CoordinatorConfig(AppConfig):
    name = 'coordinator'

    def start_grpc_server(self):
        command = grpcrunserver.Command()
        command.handle(addrport = 'localhost:50051', max_workers = 10, use_reloader = False)

    def grpc_on_server_init(self, server, **kwargs):
        from coordinator.handlers import game_coordinator_handlers
        game_coordinator_handlers(server)

    def ready(self):
        grpc_server_init.connect(self.grpc_on_server_init)

        grpc_thread        = threading.Thread(target = self.start_grpc_server)
        grpc_thread.daemon = True
        grpc_thread.start()

        try:
            from coordinator.models import Player 
            if settings.GENERATE_TEST_PLAYERS > 0:
                test_players = Player.objects.filter(is_test = True)
                if len(test_players) < settings.GENERATE_TEST_PLAYERS:
                    to_create = settings.GENERATE_TEST_PLAYERS - len(test_players)
                    for _ in range(to_create):
                        test_player = Player(email = 'test@test', is_test = True)
                        test_player.save()
                for player in list(Player.objects.filter(email = 'test@test')):
                    print(f'Test player token: {player.token}')
            if settings.KUHN_ALLOW_BOTS:
                bot_players = Player.objects.filter(is_bot = True)
                if len(bot_players) == 0:
                    bot_player = Player(email = 'bot@bot', name = 'Bot (extreme hard)', is_bot = True)
                    bot_player.save()
                    print(f'Bot player token: {bot_player.token}')


        except:
            pass
