from django.contrib import admin

from coordinator.models import Game, Player, GameLog

class PlayerAdmin(admin.ModelAdmin):
    list_display = ('token', 'public_token', 'name', 'email', 'is_disabled', 'is_test', 'is_bot')
    list_filter = ('token', 'public_token', 'name', 'email', 'is_disabled', 'is_test', 'is_bot')
    readonly_fields = ('token', 'public_token', 'is_test', 'is_bot')

    class Meta:
        model = Player

class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_started', 'is_finished', 'is_failed', 'is_private', 'created_at', 'player_1', 'player_2', 'winner_id', 'kuhn_type', 'player_type')
    list_filter = ('is_started', 'is_finished', 'is_failed', 'is_private', 'player_1', 'player_2', 'winner_id', 'kuhn_type', 'player_type')

    readonly_fields = ('is_started', 'is_finished', 'is_failed', 'is_private',
                       'error', 'created_by', 'created_at', 'player_1', 'player_2', 'outcome',
                       'winner_id', 'kuhn_type', 'player_type')

    class Meta:
        model = Game

class GameLogAdmin(admin.ModelAdmin):
    list_display = ('game_id', 'index', 'time_seconds', 'type', 'content')
    list_filter = ('game_id', 'type')

    readonly_fields = ('game_id', 'index', 'created_at', 'type', 'content')

    class Meta:
        model = Game

    def time_seconds(self, obj):
        return obj.created_at.strftime('%b %d %H:%M:%S.%f')

# Register your models here.
admin.site.register(Player, PlayerAdmin)
admin.site.register(Game, GameAdmin)
admin.site.register(GameLog, GameLogAdmin)
