import queue
import threading
import logging
from enum import Enum

from coordinator.kuhn.kuhn_waiting_room import KuhnWaitingRoom

from coordinator.models import GameCoordinator, GameCoordinatorTypes, Player, WaitingRoom

class KuhnCoordinatorEventTypes(Enum):
    Completed = 1
    Error = 2

class KuhnCoordinator(object):

    class CoordinatorWaitingRoomCreationFailed(Exception):
        pass

    def __init__(self, created_by: Player, coordinator_type: int, game_type: int, capacity: int, timeout: int, is_private: bool):

        # First do simple checks
        if (coordinator_type == GameCoordinatorTypes.DUEL_PLAYER_BOT or coordinator_type == GameCoordinatorTypes.DUEL_PLAYER_PLAYER) and capacity != 2:
            raise ValueError('Capacity should be set to 2 in case of the duel')

        if (coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS or coordinator_type == GameCoordinatorTypes.TOURNAMENT_PLAYERS_WITH_BOTS) and (capacity <= 2 or (capacity & (capacity-1) != 0)):
            raise ValueError('Capacity should be set to be a number of power of two in case of the tournament')        

        dbcoordinator = GameCoordinator(
            coordinator_type = coordinator_type,
            game_type        = game_type,
            is_private       = is_private,
            created_by       = created_by
        )
        dbcoordinator.save()
        
        self.id               = str(dbcoordinator.id)
        self.lock             = threading.RLock()
        self.coordinator_type = coordinator_type
        self.game_type        = game_type
        self.is_private       = is_private
        self.closed           = threading.Event()
        self.logger           = logging.getLogger('kuhn.coordinator')

        try:
            self.waiting_room = KuhnWaitingRoom(dbcoordinator, capacity, timeout)
        except Exception as e:
            GameCoordinator.objects.filter(id = self.id).update(is_failed = True, error = str(e))
            self.logger.warning(f'Failed to create waiting room for coordinator { self.id }')
            raise KuhnCoordinator.CoordinatorWaitingRoomCreationFailed('Coordinator could not create waiting room')

        # Calls run in a separate thread
        threading.Thread(target = self.run).start()

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
                pass

    def run(self):

        self.logger.info(f'Coordinator { self.id } initialized `run` loop.')
        # First we just wait for players to be registered
        # is_ready = self.waiting_room.wait_ready()

        # Lets not do anything at the moment and just test current stage of the code
        is_ready = self.waiting_room.wait_ready()

        if self.waiting_room.is_closed():
            self.close(error = 'Waiting room has been closed unexpectedly.')
            return

        self.close()

        self.logger.info(f'Coordinator { self.id } successfully finalized.')

    # TODO - play game in a separate thread and wait for a queue of events
    def play_game(self, game_callback) -> queue.Queue:
        q = queue.Queue()

        def __game_callback__():
            try:
                game_callback()
            except Exception as e:
                q.put((KuhnCoordinatorEventTypes.Error, { 'error': str(e) }))

        threading.Thread(target = __game_callback__).start()

        return q
