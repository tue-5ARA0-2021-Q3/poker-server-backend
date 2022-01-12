from django.apps import AppConfig
from django.conf import settings

class CoordinatorConfig(AppConfig):
    name = 'coordinator'

    def ready(self):
        try:
            if settings.GENERATE_TEST_PLAYERS > 0:
                from coordinator.models import Player

                test_players = Player.objects.filter(email = 'test@test')
                if len(test_players) < settings.GENERATE_TEST_PLAYERS:
                    to_create = settings.GENERATE_TEST_PLAYERS - len(test_players)
                    for _ in range(to_create):
                        test_player = Player(email = 'test@test')
                        test_player.save()

                for player in list(Player.objects.filter(email = 'test@test')):
                    print(f'Test player token: {player.token}')
        except:
            pass
