from django.shortcuts import render
from coordinator.models import Game


# Create your views here.

def home_view(request, *args, **kwargs):
    return render(request, "home.html", {})


def games_view(request, *args, **kwargs):
    last_games = Game.objects.all().order_by('-created_at')[:10]
    return render(request, "games.html", {
        'last_games': last_games
    })


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
            options['game'] = game
            options['events'] = list(map(parse_event, game.outcome.split('|')))
        except:
            options['is_game_found'] = False

    return render(request, "game.html", options)


def about_view(request, *args, **kwargs):
    return render(request, "about.html", {})
