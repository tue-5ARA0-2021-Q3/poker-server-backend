
from django.shortcuts import render
from coordinator.models import Game, GameCoordinatorTypes, GameRound, Player, RoomRegistration, Tournament, TournamentRound, TournamentRoundBracketItem, TournamentRoundGame
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.conf import settings

from pages.forms import SearchGameForm, SearchTournamentForm
from pages.models import Announcement

def home_view(request, *args, **kwargs):
    return render(request, "home.html", {
        'announcements': list(Announcement.objects.filter(is_hidden = False)),
        'backend_github_url': settings.BACKEND_GITHUB_URL,
        'client_github_url': settings.CLIENT_GITHUB_URL
    })

def games_view(request, *args, **kwargs):
    return render(request, "games.html", {
        'games': Game.objects.all().order_by('-created_at')[:50],
        'form': kwargs['form'] if 'form' in kwargs else SearchGameForm()
    })

def tournaments_view(request, *args, **kwargs):
    return render(request, "tournaments.html", {
        'tournaments': Tournament.objects.filter(coordinator__isnull = False).order_by('-created_at')[:50],
        'form': kwargs['form'] if 'form' in kwargs else SearchTournamentForm()
    })

def game_search_view(request, *args, **kwargs):
    if request.method == 'POST':
        form = SearchGameForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            id = form.cleaned_data['game_or_coordinator_id']
            return HttpResponseRedirect(f'/game/{ id }/')
        return games_view(request, form = form)
    return HttpResponseRedirect("/games/")

def tournament_search_view(request, *args, **kwargs):
    if request.method == 'POST':
        form = SearchTournamentForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            id = form.cleaned_data['tournament_or_coordinator_id']
            return HttpResponseRedirect(f'/tournament/{ id }/')
        return tournaments_view(request, form = form)
    return HttpResponseRedirect("/tournaments/")
    

def game_view(request, *args, **kwargs):
    id = kwargs['game_id']

    try:
        context = {}

        game  = None
        games_by_id  = Game.objects.filter(id = id)
        games_by_cid = Game.objects.filter(created_by__id = id)

        if len(games_by_id) != 0:
            game = games_by_id[0]
        elif len(games_by_cid) != 0:
            game = games_by_cid[0]

        if game == None:
            raise ValueError() 

        context['is_game_found'] = True
        context['game']          = game
        context['rounds']        = list(GameRound.objects.filter(game__id = game.id))[:-1]

        return render(request, "game.html", context)
    except Exception as e:
        return render(request, "game.html", { 'is_game_found': False })

def leaderboard_view(request, *args, **kwargs):
    players = []
    bots    = []
    for player in Player.objects.all():
        games           = Game.objects.filter(Q(player1__token = player.token) | Q(player2__token = player.token))
        games_won       = len(list(filter(lambda game: game.winner == player, games)))
        
        registrations            = list(RoomRegistration.objects.filter(player__token = player.token))
        tournaments_participated = len(list(filter(lambda reg: reg.room.coordinator.coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS or reg.room.coordinator.coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS_WITH_BOTS, registrations))) # hello oneliners in python

        tournaments_won = Tournament.objects.filter(place1__token = player.token).count()
        games_lost = len(games) - games_won

        stats = {
            'name': player.name,
            'games_total': len(games),
            'games_won': games_won,
            'games_lost': games_lost,
            'tournaments_participated': tournaments_participated,
            'tournaments_won': tournaments_won
        }
        if not player.is_bot:
            players.append(stats)
        else:
            bots.append(stats)

    # Aggregate bot stats into a single one
    aggr_bots_stats = { 'name': 'Bots (in total)', 'games_total': 0, 'games_won': 0, 'games_lost': 0, 'tournaments_participated': 0, 'tournaments_won': 0 }

    for bot in bots:
        aggr_bots_stats['games_total']              += bot['games_total']
        aggr_bots_stats['games_won']                += bot['games_won']
        aggr_bots_stats['games_lost']               += bot['games_lost']
        aggr_bots_stats['tournaments_participated'] += bot['tournaments_participated']
        aggr_bots_stats['tournaments_won']          += bot['tournaments_won']

    leaderboard = [ *players, aggr_bots_stats ]
    leaderboard = sorted(leaderboard, key = lambda d: -d['tournaments_won'])
    
    return render(request, "leaderboard.html", { 'leaderboard': leaderboard })

def tournament_view(request, *args, **kwargs):
    try: 
        id = kwargs['tournament_id']

        tournament  = None
        tournaments_by_id  = Tournament.objects.filter(id = id)
        tournaments_by_cid = Tournament.objects.filter(coordinator__id = id)
        
        if len(tournaments_by_id) != 0:
            tournament = tournaments_by_id[0]
        elif len(tournaments_by_cid) != 0:
            tournament = tournaments_by_cid[0]

        if tournament == None:
            raise ValueError()            

        rounds = sorted(list(TournamentRound.objects.filter(tournament__id = tournament.id)), key = lambda d: d.index)

        def fetch_rounds_data(round):
            bracket_items = sorted(list(TournamentRoundBracketItem.objects.filter(round__id = round.id)), key = lambda d: d.position)
            games         = list(map(lambda bracket_item: next(iter(list(TournamentRoundGame.objects.filter(bracket_item__id = bracket_item.id))), None), bracket_items))
            brackets      = list(map(lambda tuple: { 'bracket_item': tuple[0], 'game': tuple[1] }, zip(bracket_items, games)))
            return { 'round': round, 'brackets': brackets }

        rounds_data = list(map(fetch_rounds_data, rounds))

        return render(request, "tournament.html", {
            'tournament_found': True,
            'tournament': tournament,
            'rounds': rounds_data,
        })
    except Exception as e:
        return render(request, "tournament.html", { 'tournament_found': False })