import sys

from datetime import datetime

from coordinator.models import GameLog, GameLogTypes


class GameActionsLogger(object):

    def __init__(self, game_id, info = sys.stdout, warn = sys.stdout, error = sys.stderr, write_to_database = True):
        self._game_id = game_id
        self._index = 0
        self._info = info
        self._warn = warn
        self._error = error
        self._write_to_database = write_to_database
        self._is_disabled = False

    def info(self, content):
        if not self._is_disabled:
            print(f'[{self.now()}][INFO] {content}', file = self._info)
            self.write_to_database(GameLogTypes.INFO, content)

    def warn(self, content):
        if not self._is_disabled:
            print(f'[{self.now()}][INFO] {content}', file = self._warn)
            self.write_to_database(GameLogTypes.WARN, content)

    def error(self, content):
        if not self._is_disabled:
            print(f'[{self.now()}][ERROR] {content}', file = self._error)
            self.write_to_database(GameLogTypes.ERROR, content)

    def index(self):
        self._index = self._index + 1
        return self._index

    def now(self):
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    def write_to_database(self, type, content):
        if self._write_to_database:
            log = GameLog(game_id = self._game_id, type = type, index = self.index(), content = content)
            log.save()
