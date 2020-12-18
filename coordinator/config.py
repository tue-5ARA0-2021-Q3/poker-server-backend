from django.apps import AppConfig


class CoordinatorConfig(AppConfig):
    name = 'coordinator'

    def ready(self):
        try:
            from coordinator.models import Player
            players = Player.objects.all()

            if len(list(players)) < 2:
                to_create = 2 - len(list(players))
                for _ in range(to_create):
                    default_player = Player(email = 'test@test')
                    default_player.save()

            for player in list(Player.objects.all()):
                print(f'Player {player.email}: {player.token}')
        except:
            pass
