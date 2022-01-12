

from django.http.response import JsonResponse

from coordinator.models import Game

def game_counter(request, *args, **kwargs):
    return JsonResponse({
        'counter': Game.objects.count()
    })