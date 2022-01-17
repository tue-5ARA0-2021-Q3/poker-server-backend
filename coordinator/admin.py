from django.contrib import admin

from coordinator.models import Game, GameCoordinator, Player

class PlayerAdminModelView(admin.ModelAdmin):
    list_display = ('token', 'public_token', 'name', 'email', 'is_disabled', 'is_test', 'is_bot')
    list_filter = ('token', 'public_token', 'name', 'email', 'is_disabled', 'is_test', 'is_bot')
    readonly_fields = ('token', 'public_token', 'is_test', 'is_bot')

    class Meta:
        model = Player

class GameAdminModelView(admin.ModelAdmin):
    list_display = ('id', 'created_by', 'created_at', 'is_started', 'is_finished', 'is_failed', 'player1', 'player2', 'winner', 'game_type', 'outcome', 'error')
    list_filter = ('created_by', 'is_started', 'is_finished', 'is_failed', 'player1', 'player2', 'winner', 'game_type')

    readonly_fields = ('id', 'created_by', 'created_at', 'is_started', 'is_finished', 'is_failed', 'player1', 'player2', 'winner', 'game_type', 'outcome', 'error')

    class Meta:
        model = Game

class GameCoordinatorAdminModelView(admin.ModelAdmin):
    list_display    = ('id', 'coordinator_type', 'is_started', 'is_finished', 'is_failed', 'is_private', 'created_at', 'game_type', 'error')
    list_filter    = ('id', 'coordinator_type', 'is_started', 'is_finished', 'is_failed', 'is_private', 'game_type')
    readonly_fields = ('id', 'coordinator_type', 'is_started', 'is_finished', 'is_failed', 'is_private', 'created_at', 'game_type', 'error')

    class Meta:
        model = GameCoordinator

# Register your models here.
admin.site.register(Player, PlayerAdminModelView)
admin.site.register(Game, GameAdminModelView)
admin.site.register(GameCoordinator, GameCoordinatorAdminModelView)
