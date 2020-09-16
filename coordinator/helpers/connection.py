import threading

class ConnectionStatus(object):

    def __init__(self):
        self._is_connected    = threading.Event()
        self._is_disconnected = threading.Event()
        self._is_busy_event   = threading.Event()
        self._is_busy         = threading.Condition()
    
    def wait_for_connection(self):
        while not self.is_connected():
            self._is_connected.wait()

    def wait_if_busy(self):
        self.check_status()
        with self._is_busy:
            self._is_busy_event.set()
            self._is_busy.wait()
        self._is_busy_event.clear()
        self.check_status()

    def notify_all(self, sync = False):
        self.check_status()
        if sync is True:
            self._is_busy_event.wait()
        with self._is_busy:
            self._is_busy.notify_all()

    def is_connected(self):
        return self._is_connected.is_set()

    def set_connected(self):
        self._is_connected.set()

    def is_disconnected(self):
        return self._is_disconnected.is_set()

    def set_disconnected(self):
        self._is_disconnected.set()

    def is_busy(self):
        return self._is_busy_event.is_set()

    def check_status(self):
        if not self.is_connected() or self.is_disconnected():
            raise Exception('Bad connection status')