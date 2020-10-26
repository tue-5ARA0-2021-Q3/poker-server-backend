from django.shortcuts import render
from coordinator.models import Game


# Create your views here.

def home_view(request, *args, **kwargs):
    return render(request, "home.html", {})


def game_view(request, *args, **kwargs):
    options = {}
    if 'game_id' not in kwargs:
        options[ 'is_game_id_provided' ] = False
    else:
        try:
            game = Game.objects.get(id = dict(kwargs)[ 'game_id' ])

            options[ 'is_game_found' ] = True
            options[ 'game' ] = game
        except:
            options[ 'is_game_found' ] = False

    print(options)

    return render(request, "game.html", options)


def about_view(request, *args, **kwargs):
    return render(request, "about.html", {})
