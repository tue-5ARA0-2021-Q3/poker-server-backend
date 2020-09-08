
import threading

from datetime import datetime

from coordinator.helpers.connection import ConnectionStatus

class KuhnPokerPlayerInstance(object):
    
    def __init__(self):
        self.id     = None
        self.status = ConnectionStatus()

    def is_registered(self):
        return self.id is not None

    def register(self, id):
        self.id = id
        self.status.set_connected()

    def get_id(self):
        return self.id

    def get_status(self):
        return self.status

class KuhnPokerGameStage(object):

    def __init__(self, id):
        self.stage_id       = id
        self.player_actions = []
    
    def save_player_action(self, playerid, action):
        self.player_actions.append({ id: playerid, action: action })

class KuhnPokerGameInstance(object):

    def __init__(self, gameid, verbose = True):
        self.gameid  = gameid
        self.player1 = KuhnPokerPlayerInstance()
        self.player2 = KuhnPokerPlayerInstance()
        self.stages  = []
        ## Private fields
        self._counter   = 0
        self._lock      = threading.Lock()
        self._game_over = threading.Event()
        self._verbose   = verbose

    def register_player(self, player_id):
        self.check_game_status()
        # We need to lock game instance state here to check player's registration states
        with self._lock:
            if self.player1.is_registered() is False:
                self.player1.register(player_id)
                self.__log(f'Primary player ({ player_id }) has been registered')
            elif self.player2.is_registered() is False:
                self.player2.register(player_id)
                self.__log(f'Secondary player ({ player_id }) has been registered')
            else:
                raise Exception('Invalid registration: there are two connected players in the game already')

    def wait_for_all_players(self):
        self.check_game_status()
        # Wait for a successfull connection both for primary and secondary players
        self.get_primary_player().get_status().wait_for_connection()
        self.get_secondary_player().get_status().wait_for_connection()
        self.__log('Both primary and secondary players have been connected to a game instance')

    def initiate_new_stage(self):
        self.check_game_status()
        with self._lock:
            self._counter = self._counter + 1
            new_stage = KuhnPokerGameStage(self._counter)
            self.stages.append(new_stage)
            return new_stage

    def get_primary_player(self):
        return self.player1

    def is_primary_player(self, player_id):
        return self.player1.id == player_id

    def get_secondary_player(self):
        return self.player2
    
    def is_secondary_player(self, player_id):
        return self.player2.id == player_id

    def wait_for_opponent(self, player_id):
        self.check_game_status()
        if self.is_primary_player(player_id):
            self.__log(f'Primary player waits for their opponent\'s decision')
            self.get_secondary_player().get_status().wait_if_busy()
        elif self.is_secondary_player(player_id):
            self.__log(f'Secondary player waits for their opponent\'s decision')
            self.get_primary_player().get_status().wait_if_busy()
        else:
            raise Exception(f'Invalid \'player_id\' argument ({ player_id }) passed to a wait_for_opponent() method of Kuhn poker game instance')

    def notify_opponent(self, player_id):
        self.check_game_status()
        if self.is_primary_player(player_id):
            self.__log('Primary player tries to notify their opponent of his decision')
            self.get_primary_player().get_status().notify_all()
        elif self.is_secondary_player(player_id):
            self.__log('Secondary player tries to notify their opponent of his decision')
            self.get_secondary_player().get_status().notify_all()
        else:
            raise Exception(f'Invalid \'player_id\' argument ({ player_id }) passed to a notify_opponent() method of Kuhn poker game instance')

    def finish_game(self):
        self._game_over.set()

    def is_game_over(self):
        return self._game_over.is_set()

    def check_game_status(self):
        if self.is_game_over():
            raise Exception('Invalid game status: Game is over')

    ## Private methods

    def __log(self, info):
        if self._verbose:
            current_time = datetime.now().strftime('%H:%M:%S')
            print(f'[KuhnPoker][{ self.gameid }][{ current_time }]: { info }')
    

    

