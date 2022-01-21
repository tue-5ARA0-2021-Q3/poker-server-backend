import queue
import threading
import logging
import os
import logging
import subprocess
import random
import time
import traceback
from enum import Enum
from typing import List

from django.conf import settings
from coordinator.kuhn.kuhn_constants import KUHN_TYPE_TO_STR, KuhnCoordinatorMessage, KuhnCoordinatorEventTypes
from coordinator.kuhn.kuhn_game import KuhnGame
from coordinator.kuhn.kuhn_player import KuhnGameLobbyPlayer
from coordinator.kuhn.kuhn_waiting_room import KuhnWaitingRoom

from coordinator.models import Game, GameCoordinator, GameCoordinatorTypes, Player, Tournament, TournamentRound, TournamentRoundBracketItem, TournamentRoundGame

class KuhnCoordinator(object):
    LobbyBots = []

    # Here we check is bots are enabled in server settings
    # Routine picks up `BOT_FOLDER` setting variable, iterates over subfolders,
    # checks for main.py, and adds bot executables paths in `GameCoordinatorService.game_bots`
    if settings.KUHN_ALLOW_BOTS:
        for folder in os.listdir(settings.KUHN_BOT_FOLDER):
            bot_exec = os.path.join(settings.KUHN_BOT_FOLDER, folder, 'main.py')
            if os.path.isfile(bot_exec):
                logging.info(f'[KuhnCoordinator] Kuhn game bot found in \'{ folder }\'')
                LobbyBots.append(bot_exec)

    class CoordinatorWaitingRoomCreationFailed(Exception):
        pass

    def __init__(self, coordinator_type: int, game_type: int, capacity: int, timeout: int, is_private: bool):

        # First do simple checks
        if (coordinator_type == GameCoordinatorTypes.DUEL_PLAYER_BOT or coordinator_type == GameCoordinatorTypes.DUEL_PLAYER_PLAYER) and capacity != 2:
            raise ValueError('Capacity should be set to 2 in case of the duel')

        if (coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS or coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS_WITH_BOTS) and (capacity <= 2 or (capacity & (capacity-1) != 0)):
            raise ValueError('Capacity should be set to be a number of power of two in case of the tournament')        

        dbcoordinator = GameCoordinator(
            coordinator_type = coordinator_type,
            game_type        = game_type,
            is_private       = is_private
        )
        dbcoordinator.save()
        
        self.id               = str(dbcoordinator.id)
        self.lock             = threading.RLock()
        self.coordinator_type = coordinator_type
        self.game_type        = game_type
        self.is_private       = is_private
        self.channel          = queue.Queue()
        self.registered       = threading.Event()
        self.ready            = threading.Event()
        self.botsready        = threading.Event()
        self.closed           = threading.Event()
        self.error            = None
        self.logger           = logging.getLogger('kuhn.coordinator')

        try:
            self.waiting_room = KuhnWaitingRoom(dbcoordinator, capacity, timeout)
        except Exception as e:
            GameCoordinator.objects.filter(id = self.id).update(is_failed = True, error = str(e))
            self.logger.warning(f'Failed to create waiting room for coordinator { self.id }')
            raise KuhnCoordinator.CoordinatorWaitingRoomCreationFailed('Coordinator could not create waiting room')

        # Calls `run` and `add_bots` in a separate threads
        threading.Thread(target = self.run).start()
        threading.Thread(target = self.add_bots).start()

        self.logger.info(f'Coordinator { self.id } has been created successfully')

    def is_registered(self) -> bool:
        with self.lock:
            return self.registered.is_set()

    def wait_registered(self) -> bool:
        return self.registered.wait(timeout = settings.COORDINATOR_REGISTERED_TIMEOUT)

    def mark_as_registered(self):
        with self.lock:
            if not self.is_registered():
                self.logger.info(f'Game cordinator { self.id } has been marked as registered.')
                self.registered.set()

    def is_ready(self) -> bool:
        with self.lock:
            return self.ready.is_set()

    def wait_ready(self) -> bool:
        return self.ready.wait(timeout = settings.COORDINATOR_READY_TIMEOUT)

    def mark_as_ready(self):
        with self.lock:
            if not self.is_ready():
                self.logger.info(f'Game cordinator { self.id } has been marked as ready.')
                self.ready.set()

    def is_closed(self) -> bool:
        with self.lock:
            return self.closed.is_set()

    def close(self, error = None):
        with self.lock:
            if not self.is_closed():
                if not self.is_ready():
                    self.mark_as_ready()
                is_failed, error = (False, None) if error is None else (True, str(error))
                if is_failed:
                    self.logger.warning(f'Game cordinator { self.id } closed with an error: { error }')
                self.error = error
                self.waiting_room.close(error = error) # Here we do not forget to close corresponding waiting room
                GameCoordinator.objects.filter(id = self.id).update(is_finished = True, is_failed = is_failed, error = error)
                self.closed.set()

    def are_bots_ready(self):
        with self.lock:
            return self.botsready.is_set()

    def wait_bots_ready(self):
        return self.botsready.wait(timeout = settings.COORDINATOR_READY_TIMEOUT)
    
    def mark_bots_as_ready(self):
        with self.lock:
            if not self.are_bots_ready():
                self.botsready.set()

    def add_bots(self):

        if not self.wait_registered():
            self.logger.error(f'Coordinator { self.id } failed to initialize `add_bots` procedure. Coordinator has not been registered after timeout.')
            return

        self.logger.debug(f'Coordinator { self.id } initialized `add_bots` procedure.')

        if not settings.KUHN_ALLOW_BOTS:
            pass
        elif self.coordinator_type == GameCoordinatorTypes.DUEL_PLAYER_PLAYER or self.coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS:
            pass
        else:
            bot_players = list(Player.objects.filter(is_bot = True))

            if len(bot_players) == 0:
                self.close(f'Coordinator { self.id } attempts to add bot players, but there are not registered bot players in the database.')

            if len(KuhnCoordinator.LobbyBots) == 0:
                self.close(f'Coordinator { self.id } attempts to add bot players, but there are not registered bot implementations.')

            def __spawn_bot(bot_token):
                try: 
                    bot_exec = str(random.choice(KuhnCoordinator.LobbyBots))
                    self.logger.info(f'Executing { bot_exec } bot for coordinator { self.id }.')
                    subprocess.run([ 'python', bot_exec, '--play', str(self.id), '--token', bot_token, '--cards', KUHN_TYPE_TO_STR[self.game_type] ], check = True, capture_output = True)
                    self.logger.info(f'Bot in coordinator { self.id } exited sucessfully.')
                except Exception as e:
                    self.close(error = str(e))
                    return

            # In case of duel with a bot we instantiate bot thread immediatelly
            if self.coordinator_type == GameCoordinatorTypes.DUEL_PLAYER_BOT:
                threading.Thread(target = __spawn_bot, args = [ str(random.choice(bot_players).token) ]).start()
                self.waiting_room.wait_ready()
            # In case of the tournament mode we wait for waiting room to be ready and we spawn bots if and only if there are not enough players
            # The logic here is a bit iffy, but for duel games we spawn bots immediatelly and simply wait for it to connect
            # However tournament start time is uncertain, and admin may start tournament at any time, so we don't know in advance hom many bot players should connect
            # Thus we wait for game to be `ready` and in case there are not enough players we mark it as unready again in this procedure
            # After that we spawn remaining bots and wait for waiting room to be ready again (this time admin cannot interfere with this process) and mark bot lobby as ready
            elif self.coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS_WITH_BOTS:
                self.waiting_room.wait_ready()
                    
                remaining = self.waiting_room.get_room_capacity() - self.waiting_room.get_num_registered_players()

                # Here we check if we actually have some remaining spots and unset waiting_room.ready() status
                if remaining > 0:
                    try:
                        # We sample unique bot players because waiting room implementation accepts only unique connections 
                        # In case there are not enough player lobby will close. Increase `GENERATE_BOT_PLAYERS` option in case of an error
                        bots = random.sample(bot_players, remaining)
                        self.waiting_room.mark_as_unready()
                        for bot in bots:
                            threading.Thread(target = __spawn_bot, args = [ str(bot.token) ]).start()
                    except Exception as e:
                        self.close(error = f'Could not fill tournament with players. Error: { str(e) }')

                self.waiting_room.wait_ready()

        self.mark_bots_as_ready()

    def run(self):
        try:
            if not self.wait_registered():
                self.logger.error(f'Coordinator { self.id } failed to initialize `run` procedure. Coordinator has not been registered after timeout.')
                return

            self.logger.debug(f'Coordinator { self.id } initialized `run` procedure.')

            # First we just wait for players to be registered
            self.waiting_room.wait_ready()

            # We do a series of checks here and in case of an error close coordinator without even starting any games
            if self.waiting_room.is_closed():
                raise Exception('Waiting room has been closed unexpectedly.')
            
            # After waiting room is ready we additionaly wait for bots to be ready
            # This procedure does nothing in case of a simple duel, however in case of a tournament
            # We may need to spawn bots after a waiting room has been marked as ready (to fill remaining players)
            self.wait_bots_ready()

            # We mark coordinator as ready at this point since upstream service waits for this signal
            # However this event does not mean that coordinator is not closed
            self.mark_as_ready()

            if self.waiting_room.get_num_registered_players() != self.waiting_room.get_room_capacity():
                raise Exception('Not enough players to start the game.')

            # If coordinator has not been closed we proceed with a normal coordinator logic
            # Otherwise it will be just finalized
            if not self.is_closed():
                GameCoordinator.objects.filter(id = self.id).update(is_started = True)

                tokens  = self.waiting_room.get_player_tokens()
                players = list(Player.objects.filter(token__in = tokens))

                # In case of a duel setup we simply spawn one game thread and wait for it to finish redirecting any errors in case
                if self.coordinator_type == GameCoordinatorTypes.DUEL_PLAYER_BOT or self.coordinator_type == GameCoordinatorTypes.DUEL_PLAYER_PLAYER:
                    game, winner, unlucky = self.play_duel(players)
                    if game.error != None:
                        raise Exception(game.error)
                elif self.coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS or self.coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS_WITH_BOTS:
                    # tournament, place1, place2, place3 = self.play_tournament(players)
                    self.play_tournament(players)
                else:
                    raise Exception(f'Unknown coordinator type { self.coordinator_type }')
            self.waiting_room.notify_all_players(KuhnCoordinatorMessage(event = KuhnCoordinatorEventTypes.Close))
            self.logger.debug(f'Coordinator { self.id } successfully finalized `run` procedure.')
        except Exception as e:
            # In case of any exception we simply notify all players about error in coordinator logic and close the session
            self.logger.error(f'Coordinator { self.id } failed during `run` procedure. Error: { str(e) }')
            traceback.print_exc()
            self.waiting_room.notify_all_players(KuhnCoordinatorMessage(event = KuhnCoordinatorEventTypes.Error, error = str(e)))
            self.close(error = str(e))
             # Just in case we mark it as ready here again, does nothing if coordinator has been marked as ready at this moment
            self.mark_as_ready()

    def play_duel(self, players: List[Player]): 
        if len(players) != 2:
            raise Exception(f'Invalid number of players in duel setup. len(players) = { len(players) }')

        player_tokens = list(map(lambda player: str(player.token), players))

        player1 = KuhnGameLobbyPlayer(player_tokens[0], KuhnGame.InitialBank, self.waiting_room.get_player_channel(player_tokens[0]))
        player2 = KuhnGameLobbyPlayer(player_tokens[1], KuhnGame.InitialBank, self.waiting_room.get_player_channel(player_tokens[1]))
        game    = KuhnGame(self, player1, player2, self.game_type, self.channel)

        winner, unlucky = game.play()

        return game, winner, unlucky

    def make_bracket(self, players: List[Player]):
            n = len(players)

            if not ((n & (n-1) == 0) and n != 0):
                raise Exception('New bracket can be created only if number of players is equal to the power of 2.')

            bracket      = []
            draw_players = players.copy()

            while len(draw_players) != 0:
                bracket_players = random.sample(draw_players, 2)
                bracket.append(bracket_players)
                for player in bracket_players:
                    draw_players.remove(player)
            
            return bracket

    def play_tournament(self, players: List[Player]):

        # First we create tournament bracket based on number of players
        dbtournament = Tournament.objects.get(coordinator__id = self.id)

        remaining_players = players.copy()

        round = 1

        while len(remaining_players) != 1:
            
            # We create new database record for each round
            dbround = TournamentRound(tournament = dbtournament, index = round)
            dbround.save()

            self.logger.info(f'Starting round { round } of the tournament for coordinator { self.id }')

            # We create brackets until there is only one remaining player
            bracket = self.make_bracket(remaining_players)
            winners = []

            # We create database records for all upcoming rounds in advance and save db references for later usage
            dbbrackets = []
            for (index, item) in enumerate(bracket):
                dbitem = TournamentRoundBracketItem(position = index + 1, round = dbround, player1 = item[0], player2 = item[1])
                dbitem.save()
                dbbrackets.append(dbitem)
            
            self.logger.info(f'Bracket has been created for round { round } of the tournament for coordinator { self.id }')

            # For each item in bracket we play a standard duel game and create a `TournamentRoundGame` database record at the end
            for duel, dbbracket in zip(bracket, dbbrackets):
                self.logger.info(f'Starting a single duel within the tournament for coordinator { self.id }')

                game, winner, unlucky = self.play_duel(duel)

                if winner == None or game.error != None:
                    self.logger.warning('Unfinished game in the tournament with coordinator { self.id }. Choosing random winner.')
                    random_winner_token = random.choice(duel).token
                    winner = KuhnGameLobbyPlayer(random_winner_token, None, None)

                dbgame = TournamentRoundGame(bracket_item = dbbracket, game = Game.objects.get(id = game.id))
                dbgame.save()

                winners.append(winner)

            remaining_players = list(Player.objects.filter(token__in = list(map(lambda d: d.player_token, winners))))

            round = round + 1

        Tournament.objects.filter(id = dbtournament.id).update(place1 = Player.objects.get(token = remaining_players[0].token))

        self.logger.info(f'We have a winner for a tournament: { self.id } - { remaining_players[0].token }')

        return 


