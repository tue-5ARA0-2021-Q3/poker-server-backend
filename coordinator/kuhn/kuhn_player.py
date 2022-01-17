
# Player communicates with a lobby with `KuhnGameLobbyPlayerMessage` object
# It has a `player_id` field and a corresponding `action` field in a form of a string
# Lobby has to check if `action` contains an available valid action later on
class KuhnGameLobbyPlayerMessage(object):

    def __init__(self, player_id, action):
        self.player_id = player_id
        self.action    = action

    def __str__(self):
        return f'message(player_id = { self.player_id }, action = { self.action })'


# `KuhnGameLobbyPlayer` is a simple wrapper around a player
# `player_id` speaks for itself
# `bank` current bank of the player
# `channel` is a primary communication channel between lobby and the player
# `lobby` is a reference to the lobby player is supposed to interact with
class KuhnGameLobbyPlayer(object):

    def __init__(self, token: str, bank: int, channel):
        self.player_token = token
        self.bank         = bank
        self.channel      = channel

    def send_message(self, message):
        self.channel.put(message)