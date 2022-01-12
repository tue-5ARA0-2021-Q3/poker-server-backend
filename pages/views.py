from django.shortcuts import render
from coordinator.models import Game, Player
from django.db.models import Q


# Create your views here.

def home_view(request, *args, **kwargs):
    return render(request, "home.html", {})


def fetch_game_info(game):
    player1 = '-'
    player2 = '-'
    winner = '-'

    created_by = Player.objects.get(token = game.created_by)

    if game.player_1 is not None:
        player1 = Player.objects.get(token = game.player_1)

    if game.player_2 is not None:
        player2 = Player.objects.get(token = game.player_2)

    if game.winner_id is not None:
        winner = Player.objects.get(token = game.winner_id)

    return {
        'id': game.id,
        'created_at': game.created_at,
        'created_by': created_by,
        'player1': player1,
        'player2': player2,
        'winner': winner
    }


def games_view(request, *args, **kwargs):
    return render(request, "games.html")


def game_view(request, *args, **kwargs):
    options = {}
    if 'game_id' not in kwargs:
        options['is_game_id_provided'] = False
    else:
        try:
            game = Game.objects.get(id = dict(kwargs)['game_id'])

            def parse_event(event):
                turns, result = event.split(':')
                _, cards, *actions = turns.split('.')
                return {
                    'result': int(result),
                    'player_1_card': cards[0],
                    'player_2_card': cards[1],
                    'actions': actions
                }

            options['is_game_found'] = True
            options['game'] = fetch_game_info(game)
            options['events'] = list(map(parse_event, game.outcome.split('|')))
        except Exception as e:
            print(e)
            options['is_game_found'] = False

    return render(request, "game.html", options)


def leaderboard_view(request, *args, **kwargs):
    leaderboard = []

    for player in Player.objects.all():
        games = Game.objects.filter(Q(player_1 = player.token) | Q(player_2 = player.token))
        games_won = len(list(filter(lambda game: game.winner_id == player.token, games)))
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


def about_view(request, *args, **kwargs):
    return render(request, "about.html", {})
