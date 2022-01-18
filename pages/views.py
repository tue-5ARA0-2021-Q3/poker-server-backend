from django.shortcuts import render
from coordinator.models import Game, GameRound, Player
from django.db.models import Q


# Create your views here.

def home_view(request, *args, **kwargs):
    return render(request, "home.html", {})

def games_view(request, *args, **kwargs):
    return render(request, "games.html", {
        'games': Game.objects.all().order_by('-created_at')[:50]
    })


def game_view(request, *args, **kwargs):
    context = {}
    if 'game_id' not in kwargs:
        context['is_game_id_provided'] = False
    else:
        try:
            game = Game.objects.get(id = kwargs['game_id'])
            context['is_game_found'] = True
            context['game']   = game
            context['rounds'] = list(GameRound.objects.filter(game__id = game.id))
        except Exception as e:
            context['is_game_found'] = False
    return render(request, "game.html", context)


def leaderboard_view(request, *args, **kwargs):
    leaderboard = []
    for player in Player.objects.all():
        games      = Game.objects.filter(Q(player1__token = player.token) | Q(player2__token = player.token))
        games_won  = len(list(filter(lambda game: game.winner == player, games)))
        games_lost = len(games) - games_won
        leaderboard.append({
            'name': player.name,
            'games_total': len(games),
            'games_won': games_won,
            'games_lost': games_lost
        })
    return render(request, "leaderboard.html", {
        'leaderboard': leaderboard
    })
