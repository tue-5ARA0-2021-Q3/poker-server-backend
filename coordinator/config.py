from django.apps import AppConfig
from django.conf import settings

class CoordinatorConfig(AppConfig):
    name = 'coordinator'

    def ready(self):
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
            if settings.ALLOW_BOTS:
                bot_players = Player.objects.filter(is_bot = True)
                if len(bot_players) == 0:
                    bot_player = Player(email = 'bot@bot', name = 'Bot (extreme hard)', is_bot = True)
                    bot_player.save()
                    print(f'Bot player token: {bot_player.token}')


        except:
            pass
