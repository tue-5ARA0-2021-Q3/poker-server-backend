
import threading

from datetime import datetime

from coordinator.helpers.connection import ConnectionStatus

CHECK = 'check'
CALL = 'call'
FOLD = 'fold'
BET = 'bet'

class KuhnPokerPlayerInstance(object):
    initial_bank = 10
    
    def __init__(self):
        self.id     = None
        self.status = ConnectionStatus()
        self.bank   = KuhnPokerPlayerInstance.initial_bank
        # private fields
        self._lock = threading.Lock()

    def is_registered(self):
        return self.id is not None

    def register(self, id):
        self.id = id
        self.status.set_connected()

    def get_id(self):
        return self.id

    def get_status(self):
        return self.status

    def set_current_bank(self, bank):
        with self._lock:
            self.bank = bank

    def get_current_bank(self):
        with self._lock:
            return self.bank

class KuhnPokerGameInstance(object):

    def __init__(self, gameid, verbose = True):
        self.gameid  = gameid
        self.player1 = KuhnPokerPlayerInstance()
        self.player2 = KuhnPokerPlayerInstance()
        self.root    = None
        self.stage   = None
        ## Private fields
        self._counter   = 0
        self._lock      = threading.Lock()
        self._game_over = threading.Event()
        self._verbose   = verbose

    def register_player(self, player_id):
        self.check_game_status()
        # We need to lock game instance state here to check player's registration states
        with self._lock:
            if self.player1.get_id() == player_id or self.player2.get_id() == player_id:
                raise Exception('Invalid registration: there is a player with the same id in the game')
            if self.player1.is_registered() is False:
                self.player1.register(player_id)
                self.__log(f'Primary player ({ player_id }) has been registered')
            elif self.player2.is_registered() is False:
                self.player2.register(player_id)
                self.__log(f'Secondary player ({ player_id }) has been registered')
            else:
                raise Exception('Invalid registration: there are two connected players in the game')

    def wait_for_all_players(self):
        self.check_game_status()
        # Wait for a successfull connection both for primary and secondary players
        self.get_primary_player().get_status().wait_for_connection()
        self.get_secondary_player().get_status().wait_for_connection()
        self.__log('Both primary and secondary players have been connected to a game instance')

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

    def is_opponent_waiting(self, player_id):
        # self.check_game_status()
        if self.is_primary_player(player_id):
            return self.get_secondary_player().get_status().is_busy()
        elif self.is_secondary_player(player_id):
            return self.get_primary_player().get_status().is_busy()
        else: 
            raise Exception(f'Invalid \'player_id\' argument ({ player_id }) passed to a is_opponent_waiting() method of Kuhn poker game instance')

    def notify_opponent(self, player_id, sync = False):
        self.check_game_status()
        if self.is_primary_player(player_id):
            self.__log('Primary player tries to notify their opponent of his decision')
            self.get_primary_player().get_status().notify_all(sync = sync)
        elif self.is_secondary_player(player_id):
            self.__log('Secondary player tries to notify their opponent of his decision')
            self.get_secondary_player().get_status().notify_all(sync = sync)
        else:
            raise Exception(f'Invalid \'player_id\' argument ({ player_id }) passed to a notify_opponent() method of Kuhn poker game instance')

    def update_players_bank(self):
        self.player1.set_current_bank(self.player1.get_current_bank() + self.stage.evaluation())
        self.player2.set_current_bank(self.player2.get_current_bank() - self.stage.evaluation())

    def game_result(self, player_id):
        if self.is_primary_player(player_id):
            if self.player1.get_current_bank() > self.player1.get_current_bank():
                return 'win'
            else:
                return 'defeat'
        elif self.is_secondary_player(player_id):
            if self.player1.get_current_bank() > self.player1.get_current_bank():
                return 'defeat'
            else:
                return 'win'
        else:
           raise Exception(f'Invalid \'player_id\' argument ({ player_id }) passed to a game_result() method of Kuhn poker game instance') 

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
    

    

