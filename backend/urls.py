"""backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls import include
from django.shortcuts import redirect
from django.contrib import admin
from django.urls import path

from pages.views import game_search_view, home_view, games_view, game_view, leaderboard_view, tournament_search_view, tournament_view, tournaments_view
from pages.api import game_counter

urlpatterns = [
    path('', lambda req: redirect('/home/')),
    path('home/', home_view, name = 'home'),
    path('games/', games_view, name = 'games'),
    path('game/', game_search_view, name = 'game_search'),
    path('game/<str:game_id>/', game_view, name = 'game'),
    path('leaderboard/', leaderboard_view, name = 'leaderboard'),
    path('tournaments/', tournaments_view, name = 'tournaments'),
    path('tournament/', tournament_search_view, name = 'tournament_search'),
    path('tournament/<str:tournament_id>/', tournament_view, name = 'tournament'),
    path('admin/', admin.site.urls),
    path('logs/', include('log_viewer.urls')),
    path('api/game_counter', game_counter),
]

from coordinator.services import GameCoordinatorService
from proto.game import game_pb2_grpc

def grpc_handlers(server):
    game_pb2_grpc.add_GameCoordinatorControllerServicer_to_server(GameCoordinatorService.as_servicer(), server)