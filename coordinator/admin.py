from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from coordinator.models import Game, GameCoordinator, GameRound, Player, RoomRegistration, Tournament, WaitingRoom

def linkify(field_name):
    """
    Converts a foreign key value into clickable links.
    
    If field_name is 'parent', link text will be str(obj.parent)
    Link will be admin url for the admin url for obj.parent.id:change
    """
    def _linkify(obj):
        linked_obj = getattr(obj, field_name)
        if linked_obj is None:
            return '-'
        app_label = linked_obj._meta.app_label
        model_name = linked_obj._meta.model_name
        view_name = f'admin:{app_label}_{model_name}_change'
        link_url = reverse(view_name, args=[linked_obj.pk])
        return format_html('<a href="{}">{}</a>', link_url, linked_obj)

    _linkify.short_description = field_name  # Sets column name
    return _linkify

@admin.register(Player)
class PlayerAdminModelView(admin.ModelAdmin):
    list_display    = ('token', 'public_token', 'name', 'is_disabled', 'is_test', 'is_bot')
    list_filter     = ('token', 'public_token', 'name', 'is_disabled', 'is_test', 'is_bot')
    readonly_fields = ('token', 'public_token', 'is_test', 'is_bot')

@admin.register(GameCoordinator)
class GameCoordinatorAdminModelView(admin.ModelAdmin):
    list_display    = ('id', 'coordinator_type', 'is_started', 'is_finished', 'is_failed', 'is_private', 'created_at', 'game_type', 'error')
    list_filter     = ('coordinator_type', 'is_started', 'is_finished', 'is_failed', 'is_private', 'game_type', ('error', admin.EmptyFieldListFilter))
    readonly_fields = ('id', 'coordinator_type', 'is_started', 'is_finished', 'is_failed', 'is_private', 'created_at', 'game_type', 'error')

@admin.register(WaitingRoom)
class WaitingRoomAdminModelView(admin.ModelAdmin):
    list_display    = ('id', linkify('coordinator'), 'capacity', 'registered', 'timeout', 'ready', 'closed', 'error')
    list_filter     = ('capacity', 'ready', 'closed', ('error', admin.EmptyFieldListFilter))
    search_fields   = ('id', 'coordinator__id')
    readonly_fields = ('id', 'coordinator', 'capacity', 'registered', 'timeout', 'ready', 'closed', 'error')

@admin.register(RoomRegistration)
class RoomRegistrationAdminModelView(admin.ModelAdmin):
    list_display = ('id', linkify('room'), linkify('player'))
    list_filter  = ()
    search_fields = ('room__id', 'player__token')
    readonly_fields = ('id', 'room', 'player')

@admin.register(Game)
class GameAdminModelView(admin.ModelAdmin):
    list_display    = ('id', linkify('created_by'), 'created_at', 'is_started', 'is_finished', 'is_failed', linkify('player1'), linkify('player2'), linkify('winner'), 'game_type', 'error')
    list_filter     = ('is_started', 'is_finished', 'is_failed', ('winner', admin.EmptyFieldListFilter), 'game_type')
    search_fields   = ('id', 'created_by__id', 'player1__token', 'player2__token', 'winner__token')
    readonly_fields = ('id', 'created_by', 'created_at', 'is_started', 'is_finished', 'is_failed', 'player1', 'player2', 'winner', 'game_type', 'error')

@admin.register(GameRound)
class GameRoundAdminModelView(admin.ModelAdmin):
    list_display    = (linkify('game'), linkify('first'), linkify('second'), 'cards', 'index', 'inf_set', 'evaluation')
    search_fields   = ('game__id', 'first__token', 'second__token')
    readonly_fields = ('game', 'first', 'second', 'cards', 'index', 'inf_set', 'evaluation')

@admin.register(Tournament)
class TournamentAdminModelView(admin.ModelAdmin):
    list_display    = ('id', linkify('coordinator'), linkify('place1'), linkify('place2'), linkify('place3'), 'timeout', 'capacity', 'allow_bots', 'is_started', 'game_type')
    list_filter     = ('is_started', 'allow_bots', 'capacity')
    search_fields   = ('id', 'coordinator_id', 'place1__token', 'place2__token', 'place3__token')
    readonly_fields = ('id', 'coordinator', 'place1', 'place2', 'place3')