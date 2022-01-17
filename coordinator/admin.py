from django.contrib import admin

from coordinator.models import Game, GameCoordinator, Player, GameLog

class PlayerAdminModelView(admin.ModelAdmin):
    list_display = ('token', 'public_token', 'name', 'email', 'is_disabled', 'is_test', 'is_bot')
    list_filter = ('token', 'public_token', 'name', 'email', 'is_disabled', 'is_test', 'is_bot')
    readonly_fields = ('token', 'public_token', 'is_test', 'is_bot')

    class Meta:
        model = Player

# TODO adjust
class GameAdminModelView(admin.ModelAdmin):
    list_display = ('id', 'is_started', 'is_finished', 'is_failed', 'is_private', 'created_at', 'player_1', 'player_2', 'winner_id', 'kuhn_type', 'player_type')
    list_filter = ('is_started', 'is_finished', 'is_failed', 'is_private', 'player_1', 'player_2', 'winner_id', 'kuhn_type', 'player_type')

    readonly_fields = ('is_started', 'is_finished', 'is_failed', 'is_private',
                       'error', 'created_by', 'created_at', 'player_1', 'player_2', 'outcome',
                       'winner_id', 'kuhn_type', 'player_type')

    class Meta:
        model = Game

# TODO remove
class GameLogAdminModelView(admin.ModelAdmin):
    list_display = ('game_id', 'index', 'time_seconds', 'type', 'content')
    list_filter = ('game_id', 'type')

    readonly_fields = ('game_id', 'index', 'created_at', 'type', 'content')

    class Meta:
        model = Game

    def time_seconds(self, obj):
        return obj.created_at.strftime('%b %d %H:%M:%S.%f')

class GameCoordinatorAdminModelView(admin.ModelAdmin):
    list_display    = ('id', 'coordinator_type', 'is_started', 'is_finished', 'is_failed', 'is_private', 'created_at', 'game_type', 'error')
    list_filter    = ('id', 'coordinator_type', 'is_started', 'is_finished', 'is_failed', 'is_private', 'game_type')
    readonly_fields = ('id', 'coordinator_type', 'is_started', 'is_finished', 'is_failed', 'is_private', 'created_at', 'game_type', 'error')

    class Meta:
        model = GameCoordinator

# Register your models here.
admin.site.register(Player, PlayerAdminModelView)
admin.site.register(Game, GameAdminModelView)
admin.site.register(GameLog, GameLogAdminModelView)
admin.site.register(GameCoordinator, GameCoordinatorAdminModelView)
