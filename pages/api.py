import itertools
from uuid import UUID

from django.http.response import JsonResponse
from django.core import serializers

from coordinator.models import Game, Player

def game_counter(request, *args, **kwargs):
    return JsonResponse({
        'counter': Game.objects.count()
    })

def last_games(request, *args, **kwargs):
    last_games = Game.objects.all().order_by('-created_at')[:50].values('player_1', 'player_2', 'winner_id', 'id', 'created_at')
    # Filter out all possible filter ids needed for last games query
    player_ids = list(set(filter(lambda d: isinstance(d, UUID), itertools.chain.from_iterable(map(lambda d: d.values(), last_games)))))
    players    = Player.objects.filter(token__in=player_ids).values('name', 'token', 'public_token')

    # We create token -> public_token mapping to hide real player tokens
    player_public_mapping = {
        player['token']:player for player in players
    }
    player_public_mapping[None] = {
        'public_token': None
    }

    # This functions replaces player token with their public equivalents
    # Public token cannot be used to initiate a game
    def hidePrivateTokensInGame(game):
        game['player_1']  = player_public_mapping[game['player_1']]['public_token']
        game['player_2']  = player_public_mapping[game['player_2']]['public_token']
        game['winner_id'] = player_public_mapping[game['winner_id']]['public_token']
        return game

    last_games = list(map(hidePrivateTokensInGame, last_games))
    players    = dict(zip(map(lambda d: str(d['public_token']), players), map(lambda d: { 'name':d['name'] }, players)))

    return JsonResponse({
        'games': last_games,
        'players': players
    })