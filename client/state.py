class GameState(object):

    def __init__(self):
        self._history = [[]]
        self._available_actions = []

    def save_action_in_history(self, action, last = False):
        self._history[-1].append(action)
        if last:
            self._history.append([])
        return self._history

    def set_available_actions(self, new_available_actions):
        self._available_actions = new_available_actions
        return self._available_actions

    def history(self):
        return self._history

    def available_actions(self):
        return self._available_actions
