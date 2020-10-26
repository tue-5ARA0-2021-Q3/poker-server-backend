import threading
import collections


class ClientRequestEventsIterator(object):

    def __init__(self):
        self.request_condition = threading.Condition()
        self.request_lock = threading.Lock()
        self.requests = collections.deque()
        self.stop_event = threading.Event()

    def _next(self):
        with self.request_condition:
            while not self.requests and not self.stop_event.is_set():
                self.request_condition.wait()
            with self.request_lock:
                if len(self.requests) > 0:
                    return self.requests.popleft()
                else:
                    raise StopIteration()

    def next(self):
        return self._next()

    def __next__(self):
        return self._next()

    def set_initial_request(self, request):
        with self.request_lock:
            self.requests.append(request)

    def make_request(self, request):
        with self.request_lock:
            self.requests.append(request)
            with self.request_condition:
                self.request_condition.notify_all()

    def close(self):
        self.stop_event.set()
        with self.request_condition:
            self.request_condition.notify_all()

    def is_closed(self):
        return self.stop_event.is_set()
