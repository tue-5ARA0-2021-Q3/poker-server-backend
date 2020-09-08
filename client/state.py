
class GameState(object):

    def __init__(self):
        self._history           = []
        self._available_actions = [ 'continue', 'end' ]

    def save_action_in_history(self, action):
        return self._history.append(action)

    def set_available_actions(self, new_available_actions):
        self._available_actions = new_available_actions
        return self._available_actions

    def history(self):
        return self._history

    def available_actions(self):
        return self._available_actions