import queue
import threading
import logging
import os
import logging
import subprocess
import random
from enum import Enum

from django.conf import settings
from coordinator.kuhn.kuhn_constants import KUHN_TYPE_TO_STR
from coordinator.kuhn.kuhn_waiting_room import KuhnWaitingRoom

from coordinator.models import GameCoordinator, GameCoordinatorTypes, Player, WaitingRoom

class KuhnCoordinatorEventTypes(Enum):
    Completed = 1
    Error = 2

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
        self.closed           = threading.Event()
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

    def is_closed(self) -> bool:
        with self.lock:
            return self.closed.is_set()

    def close(self, error = None):
        with self.lock:
            if not self.is_closed():
                is_failed, error = (False, None) if error is None else (True, str(error))
                if is_failed:
                    self.logger.warning(f'Game cordinator { self.id } closed with an error: { error }')
                self.waiting_room.close(error = error) # Here we do not forget to close corresponding waiting room
                GameCoordinator.objects.filter(id = self.id).update(is_finished = True, is_failed = is_failed, error = error)
                self.closed.set()

    def add_bots(self):

        if not settings.KUHN_ALLOW_BOTS:
            return

        if self.coordinator_type == GameCoordinatorTypes.DUEL_PLAYER_PLAYER or self.coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS:
            return
        
        bot_players = Player.objects.filter(is_bot = True)

        if len(bot_players) == 0:
            self.close(f'Coordinator { self.id } attempts to add bot players, but there are not registered bot players in the database.')

        bot_player = random.choice(bot_players)
        bot_token  = str(bot_player.token)

        if len(KuhnCoordinator.LobbyBots) == 0:
            self.close(f'Coordinator { self.id } attempts to add bot players, but there are not registered bot implementations.')

        # In case of duel with a bot we instantiate bot thread immediatelly
        if self.coordinator_type == GameCoordinatorTypes.DUEL_PLAYER_PLAYER:
            try: 
                bot_exec = str(random.choice(KuhnCoordinator.LobbyBots))
                self.logger.info(f'Executing { bot_exec } bot for coordinator { self.id }.')
                subprocess.run([ 'python', bot_exec, '--play', self.id, '--token', bot_token, '--cards', KUHN_TYPE_TO_STR[self.game_type] ], check = True, capture_output = True)
                self.logger.info(f'Bot in coordinator { self.id } exited sucessfully.')
            except Exception as e:
                self.close(error = str(e))
        elif self.coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS_WITH_BOTS:
            self.close(error = 'Not implemented: GameCoordinatorTypes.TOURNAMENT_PLAYERS_WITH_BOTS')

        return

    def run(self):

        self.logger.info(f'Coordinator { self.id } initialized `run` loop.')
        # First we just wait for players to be registered

        # Lets not do anything at the moment and just test current stage of the code
        is_ready = self.waiting_room.wait_ready()

        if self.waiting_room.is_closed():
            self.close(error = 'Waiting room has been closed unexpectedly.')
            return
        elif not is_ready:
            self.close(error = 'Waiting room have not enough players after timeout.')
            return

        self.close()
        self.logger.info(f'Coordinator { self.id } successfully finalized.')

    @staticmethod
    def play_duel(player1: Player, player2: Player): 
        pass
